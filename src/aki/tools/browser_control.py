"""Browser control tools using Playwright with CDP integration"""

import logging
import chainlit as cl
from typing import Optional, Dict, List, Any, Type
from pydantic import BaseModel, Field
from langchain_core.tools import BaseTool
from langchain_core.callbacks import CallbackManagerForToolRun
from playwright.async_api import async_playwright, Browser, Page, CDPSession
import asyncio
import os
import base64
from datetime import datetime
import uuid


class BrowserSettings(BaseModel):
    viewport: dict = Field(
        default={"width": 1024, "height": 768}, description="Browser viewport settings"
    )
    headless: bool = Field(
        default=True, description="Whether to run browser in headless mode"
    )


class BrowserAction(BaseModel):
    """Input schema for BrowserActionTool."""

    action: str = Field(
        description="Action to perform (launch, click, type, scroll_down, scroll_up, snapshot, close)"
    )
    session_id: Optional[str] = Field(
        default=None,
        description="Session ID for the browser instance (required for all actions except launch)",
    )
    url: Optional[str] = Field(
        default=None, description="URL to navigate to (for launch action)"
    )
    file: Optional[str] = Field(
        default=None,
        description="File path to open (for launch action). If relative, will be converted to absolute file:// URL",
    )
    coordinate: Optional[str] = Field(
        default=None, description="x,y coordinates for click action (e.g. '450,300')"
    )
    text: Optional[str] = Field(
        default=None, description="Text to type (for type action)"
    )


class BrowserSessionManager:
    """Manages multiple browser sessions."""

    def __init__(self):
        self._sessions: Dict[str, "BrowserSession"] = {}

    async def create_session(self) -> str:
        """Create a new browser session and return its ID."""
        session_id = str(uuid.uuid4())
        self._sessions[session_id] = BrowserSession()
        return session_id

    def get_session(self, session_id: str) -> Optional["BrowserSession"]:
        """Get a browser session by ID."""
        return self._sessions.get(session_id)

    async def close_session(self, session_id: str) -> None:
        """Close and remove a browser session."""
        if session_id in self._sessions:
            await self._sessions[session_id].close()
            del self._sessions[session_id]

    def list_active_sessions(self) -> List[str]:
        """List all active session IDs."""
        return [sid for sid, session in self._sessions.items() if session.is_active]


class BrowserSession:
    def __init__(self):
        self._browser: Optional[Browser] = None
        self._page: Optional[Page] = None
        self._cdp: Optional[CDPSession] = None
        self.settings = BrowserSettings()
        self._console_logs: List[str] = []
        self._action_logs: List[str] = []
        self._page_info: Optional[Dict] = None
        self._is_active: bool = False
        self._mouse_position: Optional[Dict[str, int]] = None
        logging.info("BrowserSession initialized with default state")

    @property
    def is_active(self) -> bool:
        """Check if the browser session is active."""
        return self._is_active

    async def _handle_console(self, msg):
        """Handle console messages from the page"""
        text = f"[{msg.type}] {msg.text}"
        self._console_logs.append(text)
        logging.debug(f"Browser console: {text}")

    async def _handle_page_error(self, error):
        """Handle page errors"""
        text = f"[Page Error] {str(error)}"
        self._console_logs.append(text)
        logging.error(text)

    async def launch(self, url: str) -> Dict:
        """Launch browser and navigate to URL"""
        logging.info("Launch requested with URL: %s", url)
        if self._browser:
            logging.info("Existing browser found, closing first")
            await self.close()

        logging.info("Starting new browser session")
        playwright = await async_playwright().start()
        self._browser = await playwright.chromium.launch(
            headless=self.settings.headless
        )
        logging.info("Browser launched with headless=%s", self.settings.headless)

        # Create browser context and page
        context = await self._browser.new_context()
        self._page = await context.new_page()

        # Initialize CDP session
        self._cdp = await self._page.context.new_cdp_session(self._page)
        await self._setup_cdp_listeners()

        # Initialize state
        self._page_info = None
        self._action_logs = ["Launching browser..."]
        self._console_logs = []
        self._mouse_position = None
        self._is_active = True  # Set active immediately
        logging.info("Browser state initialized: is_active=%s", self._is_active)

        # Set viewport
        await self._page.set_viewport_size(self.settings.viewport)
        self._console_logs.append(f"[Debug] Viewport set to {self.settings.viewport}")

        try:
            # Launch browser and navigate
            self._action_logs.append(f"Browser launched, navigating to {url}")
            self._console_logs.append("[Debug] Browser launched successfully")

            # Navigate to URL
            await self._page.goto(url, wait_until="networkidle", timeout=7000)
            await self._wait_till_html_stable()

            # Update page info after navigation
            content = await self._page.content()
            title = await self._page.title()

            # Ensure content is properly formatted HTML
            if content and not content.strip().startswith("<!DOCTYPE html>"):
                content = f"<!DOCTYPE html><html><body>{content}</body></html>"

            self._page_info = {
                "content": content,
                "url": self._page.url,
                "title": title,
                "timestamp": str(datetime.now()),  # Add timestamp for debugging
            }
            logging.info(
                f"Page info prepared: title={title}, url={self._page.url}, content_length={len(content) if content else 0}"
            )
            self._console_logs.append(f"[Debug] Page loaded: {title}")
            self._console_logs.append(f"[Debug] Page title: {await self._page.title()}")
            self._console_logs.append(f"[Debug] Content sample: {content[:200]}...")
            self._action_logs.append("Page loaded successfully")
            self._console_logs.append(f"[Debug] Content length: {len(content)}")
            self._console_logs.append(f"[Debug] URL: {self._page.url}")
            return await self._capture_state()
        except Exception as e:
            self._console_logs.append(f"[Error] {str(e)}")
            self._action_logs.append(f"Error during navigation: {str(e)}")
            # Try to get content even if navigation failed
            if self._page:
                try:
                    content = await self._page.content()
                    title = await self._page.title()
                    self._page_info = {
                        "content": content,
                        "url": self._page.url,
                        "title": title,
                        "timestamp": str(datetime.now()),
                    }
                    self._console_logs.append("[Debug] Retrieved content after error")
                    # Keep browser active if we got content successfully
                    self._is_active = True
                except Exception as inner_e:
                    self._console_logs.append(
                        f"[Error] Failed to get content: {str(inner_e)}"
                    )
                    self._page_info = None
                    self._is_active = False
            return await self._capture_state()

    async def _wait_till_html_stable(self, timeout: int = 5000):
        """Wait until page HTML stabilizes"""
        check_interval = 500
        max_checks = timeout // check_interval
        last_html_size = 0
        stable_iterations = 0
        min_stable_iterations = 3

        for _ in range(max_checks):
            html = await self._page.content()
            current_size = len(html)

            if last_html_size == current_size:
                stable_iterations += 1
            else:
                stable_iterations = 0

            if stable_iterations >= min_stable_iterations:
                logging.debug("Page rendered fully")
                break

            last_html_size = current_size
            await asyncio.sleep(check_interval / 1000)

    async def _setup_cdp_listeners(self):
        """Setup CDP event listeners"""
        if not self._cdp:
            return

        # Enable necessary domains
        await self._cdp.send("Network.enable")
        await self._cdp.send("Page.enable")
        await self._cdp.send("Runtime.enable")

        # Setup event handlers
        self._cdp.on("Runtime.consoleAPICalled", self._handle_cdp_console)
        self._cdp.on("Network.responseReceived", self._handle_cdp_network_response)

    def _handle_cdp_console(self, event: Dict):
        """Handle CDP console events"""
        msg_type = event.get("type", "log")
        args = event.get("args", [])
        text = " ".join(str(arg.get("value", "")) for arg in args)
        self._console_logs.append(f"[{msg_type}] {text}")

    def _handle_cdp_network_response(self, event: Dict):
        """Handle CDP network response events"""
        response = event.get("response", {})
        if response.get("status", 0) >= 400:
            self._console_logs.append(
                f"Network error: {response.get('status')} - {response.get('statusText')}"
            )

    async def click(self, coordinate: str) -> Dict:
        """Click at specified coordinates"""
        if not self._page or not self._cdp:
            raise Exception("Browser not launched")

        x, y = map(int, coordinate.split(","))
        self._action_logs.append(f"Clicked at coordinates ({x}, {y})")
        self._mouse_position = {"x": x, "y": y}

        # Use CDP to simulate click
        await self._cdp.send(
            "Input.dispatchMouseEvent",
            {"type": "mousePressed", "x": x, "y": y, "button": "left", "clickCount": 1},
        )

        await self._cdp.send(
            "Input.dispatchMouseEvent",
            {
                "type": "mouseReleased",
                "x": x,
                "y": y,
                "button": "left",
                "clickCount": 1,
            },
        )

        # Wait for any navigation or network activity
        try:
            await self._page.wait_for_load_state("networkidle", timeout=7000)
            await self._wait_till_html_stable()
        except Exception:
            pass  # No navigation occurred

        # Update page info after click
        content = await self._page.content()
        self._page_info = {
            "content": content,  # Send raw content without escaping
            "url": self._page.url,
            "title": await self._page.title(),
        }
        return await self._capture_state()

    async def type(self, text: str) -> Dict:
        """Type text"""
        if not self._page or not self._cdp:
            raise Exception("Browser not launched")

        # Use CDP to simulate typing
        for char in text:
            await self._cdp.send(
                "Input.dispatchKeyEvent", {"type": "keyDown", "text": char}
            )
            await self._cdp.send(
                "Input.dispatchKeyEvent", {"type": "keyUp", "text": char}
            )

        self._action_logs.append(f"Typed text: {text}")
        content = await self._page.content()
        self._page_info = {
            "content": content,  # Send raw content without escaping
            "url": self._page.url,
            "title": await self._page.title(),
        }
        return await self._capture_state()

    async def snapshot(self) -> Dict:
        """Capture current browser state without performing any action."""
        if not self._is_active:
            raise Exception("Browser session is not active")
        return await self._capture_state()

    async def scroll(self, direction: str) -> Dict:
        """Scroll the page"""
        if not self._page:
            raise Exception("Browser not launched")

        scroll_amount = 600 if direction == "down" else -600
        await self._page.evaluate(f"window.scrollBy(0, {scroll_amount})")
        self._action_logs.append(f"Scrolled {direction}")
        await asyncio.sleep(0.3)

        # Update page info after scrolling
        content = await self._page.content()
        self._page_info = {
            "content": content,  # Send raw content without escaping
            "url": self._page.url,
            "title": await self._page.title(),
        }
        return await self._capture_state()

    async def close(self) -> Dict:
        """Close the browser"""
        if self._cdp:
            await self._cdp.detach()
            self._cdp = None

        if self._browser:
            await self._browser.close()
            self._browser = None
            self._page = None
            self._action_logs.append("Browser closed")
            self._page_info = None
            self._is_active = False
            self._console_logs = []
            self._mouse_position = None

        return await self._capture_state()

    async def _capture_state(self) -> Dict:
        """Capture current browser state including screenshot"""
        try:
            state = {
                "page_info": self._page_info,
                "is_active": self._is_active,
                "logs": self._action_logs,
                "console_logs": self._console_logs,
                "current_url": self._page.url if self._page else None,
                "mouse_position": self._mouse_position,
            }

            # Capture screenshot if browser is active
            if self._page and self._is_active:
                try:
                    screenshot = await self._page.screenshot(type="png")
                    state["screenshot"] = base64.b64encode(screenshot).decode()

                except Exception as e:
                    logging.error(f"Failed to capture screenshot: {str(e)}")

            return state
        except Exception as e:
            logging.error(f"Error capturing state: {str(e)}")
            return {
                "error": str(e),
                "logs": self._action_logs or [],
                "console_logs": self._console_logs or [],
            }


class BrowserActionTool(BaseTool):
    """Tool for controlling browser instances to interact with web pages, HTML files, and interactive games."""

    name: str = "browser_action"
    args_schema: Type[BaseModel] = BrowserAction

    def __init__(self):
        super().__init__()
        self._session_manager = BrowserSessionManager()
        self._message_cache: Dict[str, Any] = {}

    description: str = """
    Control a browser instance to interact with web pages, HTML files, and interactive games.

    The browser window has a fixed resolution of 1024x768 pixels. When performing click actions,
    ensure coordinates are within this range and target the center of elements.

    IMPORTANT INTERACTION GUIDELINES:
    1. After EACH action:
       - Carefully analyze the returned screenshot
       - Verify if the action had the intended effect
       - Look for any state changes or feedback messages
       - Plan next action based on the verified current state
       - If unexpected results, explain what happened and adjust strategy

    2. For click actions:
       - Calculate positions relative to the 1024x768 viewport
       - Target the center of interactive elements
       - Verify click location had the intended effect
       - Consider alternative coordinates if interaction fails

    Common Use Cases:
    1. Opening and reading HTML files:
       - Use file parameter for local HTML files (automatically converts to file:// URL)
       - Or use url parameter with file:/// protocol directly
       - Example: file="path/to/file.html" or url="file:///absolute/path/to/file.html"
       
    2. Interactive applications:
       - Launch HTML-based applications and control via clicks/typing
       - Observe application feedback after each action
       - Maintain awareness of application state
       - Adjust strategy based on visual feedback

    After each action, you will be given a screenshot of current browser. Carefully analyze the returned screenshot and confirm if the action is performed correctly. 
    If it's not expected, explain it and try another more likely succeed action. If you keep failing, tell the user and explain the situation.
    """

    def _run(
        self,
        action: str,
        url: Optional[str] = None,
        file: Optional[str] = None,
        coordinate: Optional[str] = None,
        text: Optional[str] = None,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        """Execute the browser action synchronously."""
        raise NotImplementedError("BrowserActionTool only supports async operations")

    async def _arun(
        self,
        action: str,
        session_id: Optional[str] = None,
        url: Optional[str] = None,
        file: Optional[str] = None,
        coordinate: Optional[str] = None,
        text: Optional[str] = None,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        """Execute the browser action asynchronously."""
        logging.info(f"Browser action called: {action}")
        logging.info(
            f"Parameters: session_id={session_id}, url={url}, file={file}, coordinate={coordinate}, text={text}"
        )
        try:
            result = {}
            session = None

            if action == "launch":
                # Create new session
                session_id = await self._session_manager.create_session()
                session = self._session_manager.get_session(session_id)

                if file:
                    # Convert file path to absolute file:// URL
                    abs_path = os.path.abspath(file)
                    url = f"file://{abs_path}"
                    logging.info(f"Converting file path to URL: {url}")
                elif not url:
                    raise ValueError(
                        "Either url or file parameter is required for launch action"
                    )

                logging.info(f"Launching browser with URL: {url}")
                result = await session.launch(url)
                logging.info(f"Launch result for session {session_id}:", result)
                result["session_id"] = session_id  # Include session ID in response

            else:
                # All other actions require a session ID
                if not session_id:
                    raise ValueError(
                        "Session ID is required for all actions except launch"
                    )

                session = self._session_manager.get_session(session_id)
                if not session:
                    raise ValueError(f"No active session found with ID: {session_id}")

                if action == "snapshot":
                    result = await session.snapshot()
                elif action == "click":
                    if not coordinate:
                        raise ValueError("Coordinate is required for click action")
                    result = await session.click(coordinate)
                elif action == "type":
                    if not text:
                        raise ValueError("Text is required for type action")
                    result = await session.type(text)
                elif action == "scroll_down":
                    result = await session.scroll("down")
                elif action == "scroll_up":
                    result = await session.scroll("up")
                elif action == "close":
                    result = await session.close()
                    await self._session_manager.close_session(session_id)
                    if session_id in self._message_cache:
                        await self._message_cache[session_id].remove()
                        del self._message_cache[session_id]
                else:
                    raise ValueError(f"Unknown action: {action}")

            # Log the state before updating viewer
            logging.info(
                f"Browser state: active={result.get('is_active')}, url={result.get('current_url')}"
            )
            if result.get("page_info"):
                logging.info(f"Page title: {result['page_info'].get('title')}")
                logging.info(
                    f"Content length: {len(result['page_info'].get('content', ''))}"
                )

            # Update browser viewer
            try:
                # Prepare page info
                page_info = result.get("page_info")
                if page_info and page_info.get("content"):
                    logging.info(f"Content length: {len(page_info['content'])}")

                # Create or update message
                elements = [
                    cl.CustomElement(
                        name="BrowserViewer",
                        props={
                            "pageInfo": page_info,  # Send raw HTML content
                            "isActive": result.get(
                                "is_active", True
                            ),  # Default to active
                            "logs": result.get("logs", []),
                            "consoleLogs": result.get("console_logs", []),
                        },
                        display="inline",
                    )
                ]

                if session_id in self._message_cache:
                    await self._message_cache[session_id].remove()

                # Create new message
                message = cl.Message(
                    elements=elements, content=f"Browser Session: {session_id}"
                )
                await message.send()
                self._message_cache[session_id] = message

            except Exception as e:
                logging.error(f"Error updating browser viewer: {str(e)}")
                logging.error("Stack trace:", exc_info=True)

            # Initialize the multimodal content list
            formatted_content = [
                {
                    "type": "text",
                    "text": f"session_id: {session_id} log: {result.get('logs', [])}",
                }
            ]

            # Process screenshot if available
            if "screenshot" in result:
                formatted_content.append(
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": result["screenshot"],
                        },
                    }
                )

            return formatted_content

        except Exception as e:
            error_msg = f"Browser action failed: {str(e)}"
            logging.error(error_msg)
            return error_msg


def create_browser_action_tool() -> BaseTool:
    """Create and return the browser action tool.

    The tool manages multiple browser sessions, each identified by a unique session ID.
    The session ID is returned by the launch action and required for all subsequent actions.
    """
    return BrowserActionTool()
