import React, { useEffect, useState } from 'react';

export default function BrowserViewer() {
    const { pageInfo, isActive, logs, consoleLogs } = props;
    
    console.log('BrowserViewer render:', {
        timestamp: new Date().toISOString(),
        isActive,
        hasPageInfo: !!pageInfo,
        logsCount: logs.length,
        consoleLogsCount: consoleLogs.length
    });

    const [status, setStatus] = useState('waiting');
    const [error, setError] = useState(null);
    const [activeTab, setActiveTab] = useState('actions');
    const [isLogsExpanded, setIsLogsExpanded] = useState(false);

    // Log component lifecycle
    useEffect(() => {
        console.log('BrowserViewer mounted');
        return () => {
            console.log('BrowserViewer unmounting');
        };
    }, []);

    // Track status changes with dependency tracking
    useEffect(() => {
        console.log('Status effect triggered:', {
            currentStatus: status,
            isActive,
            hasContent: !!pageInfo?.content,
            logsPresent: logs.length > 0,
            dependencies: {
                isActiveChanged: isActive,
                contentChanged: !!pageInfo?.content,
                logsChanged: logs.length,
                consoleLogsChanged: consoleLogs.length
            }
        });
    }, [status, isActive, pageInfo?.content, logs.length, consoleLogs.length]);

    // Track status updates
    const updateStatus = (newStatus) => {
        console.log('Status update requested:', {
            from: status,
            to: newStatus,
            trigger: {
                isActive,
                hasContent: !!pageInfo?.content,
                logsCount: logs.length
            }
        });
        setStatus(newStatus);
    };

    // Track props changes
    useEffect(() => {
        console.log('BrowserViewer props:', { 
            isActive, 
            hasPageInfo: !!pageInfo,
            hasContent: pageInfo?.content ? true : false,
            contentLength: pageInfo?.content?.length,
            title: pageInfo?.title,
            logsCount: logs.length,
            consoleLogsCount: consoleLogs.length,
            rawPageInfo: pageInfo,  // Log full pageInfo
            rawLogs: logs,          // Log full logs
            rawConsoleLogs: consoleLogs  // Log full console logs
        });

        // Reset error state on prop changes
        console.log('Resetting error state');
        setError(null);

        // Log previous state
        console.log('Previous state:', status);

        // Determine component state with detailed logging
        if (!isActive) {
            console.log('isActive is false, setting closed state');
            updateStatus('closed');
        } else if (pageInfo?.content) {
            console.log('Content found:', {
                contentLength: pageInfo.content.length,
                contentPreview: pageInfo.content.substring(0, 100),
                title: pageInfo.title,
                url: pageInfo.url
            });
            updateStatus('active');
        } else if (logs.length === 0 && consoleLogs.length === 0) {
            console.log('No logs yet, showing initializing state');
            updateStatus('waiting');
        } else {
            console.log('Browser active but no content:', {
                isActive,
                hasPageInfo: !!pageInfo,
                logsPresent: logs.length > 0,
                consoleLogsPresent: consoleLogs.length > 0
            });
            updateStatus('waiting');
        }

        // Log new state
        console.log('New state set:', status);
    }, [
        isActive,
        pageInfo?.content,
        pageInfo?.title,
        pageInfo?.url,
        logs.length,
        consoleLogs.length,
        JSON.stringify(logs),
        JSON.stringify(consoleLogs)
    ]);

    // Get HTML content with detailed logging
    const getContent = () => {
        console.log('getContent called, checking pageInfo:', {
            hasPageInfo: !!pageInfo,
            hasContent: pageInfo?.content ? true : false
        });

        if (!pageInfo?.content) {
            console.log('No content available in pageInfo');
            return '';
        }
        
        console.log('Raw content details:', {
            type: typeof pageInfo.content,
            length: pageInfo.content.length,
            sample: pageInfo.content.substring(0, 100),
            hasDoctype: pageInfo.content.includes('<!DOCTYPE'),
            hasHtmlTag: pageInfo.content.includes('<html'),
            hasHeadTag: pageInfo.content.includes('<head'),
            hasBodyTag: pageInfo.content.includes('<body')
        });
        
        try {
            // Parse HTML content
            console.log('Parsing HTML content...');
            const parser = new DOMParser();
            const doc = parser.parseFromString(pageInfo.content, 'text/html');
            
            console.log('Parsed document structure:', {
                hasDoctype: !!doc.doctype,
                hasHtmlElement: !!doc.documentElement,
                hasHead: !!doc.head,
                hasBody: !!doc.body,
                headChildNodes: doc.head?.childNodes.length,
                bodyChildNodes: doc.body?.childNodes.length
            });

            const content = doc.documentElement.innerHTML;
            console.log('Extracted innerHTML:', {
                length: content.length,
                sample: content.slice(0, 100),
                isEmpty: !content.trim()
            });
            
            if (!content.trim()) {
                console.error('Parsed content is empty');
                return '<div>Error: Empty content</div>';
            }
            
            // Build final HTML
            const head = doc.head ? doc.head.innerHTML : '';
            const body = doc.body ? doc.body.innerHTML : content;
            
            console.log('Final content parts:', {
                hasHead: !!head,
                headLength: head.length,
                hasBody: !!body,
                bodyLength: body.length
            });

            const finalHtml = `
                <!DOCTYPE html>
                <html>
                    <head>
                        ${head}
                        <base target="_blank">
                        <style>
                            /* Ensure content fills iframe */
                            html, body {
                                width: 100%;
                                height: 100%;
                                margin: 0;
                                padding: 0;
                            }
                        </style>
                    </head>
                    <body>${body}</body>
                </html>
            `;

            console.log('Final HTML details:', {
                length: finalHtml.length,
                hasDoctype: finalHtml.includes('<!DOCTYPE'),
                hasBaseTag: finalHtml.includes('<base'),
                hasStyle: finalHtml.includes('<style')
            });

            return finalHtml;
        } catch (e) {
            console.error('Error decoding content:', e);
            console.error('Raw content:', pageInfo.content);
            return '<div>Error decoding content</div>';
        }
    };

    // Handle iframe messages
    useEffect(() => {
        const handleMessage = (event) => {
            if (!event.source.frameElement) return;
            
            try {
                const data = event.data;
                if (data.type === 'error') {
                    console.error('Iframe error:', data.message);
                    setError(data.message);
                } else if (data.type === 'console') {
                    console.log('Iframe log:', data.message);
                }
            } catch (e) {
                console.error('Error handling iframe message:', e);
            }
        };

        window.addEventListener('message', handleMessage);
        return () => window.removeEventListener('message', handleMessage);
    }, []);

    // Handle iframe load with detailed logging
    const handleIframeLoad = (event) => {
        console.log('Iframe load event triggered');
        const iframe = event.target;
        
        console.log('Iframe details:', {
            hasContentWindow: !!iframe.contentWindow,
            hasContentDocument: !!iframe.contentDocument,
            readyState: iframe.contentDocument?.readyState,
            url: iframe.src || 'srcDoc content'
        });

        try {
            console.log('Resetting error state');
            setError(null);
            
            console.log('Setting up iframe handlers...');
            const script = `
                console.log('Initializing iframe handlers...');
                
                window.onerror = function(msg, url, line, col, error) {
                    const errorMsg = error ? error.stack || error.message : msg;
                    console.error('Iframe error:', errorMsg, 'at line', line);
                    window.parent.postMessage({
                        type: 'error',
                        message: \`\${errorMsg} (line \${line})\`
                    }, '*');
                    return false;
                };
                
                window.addEventListener('unhandledrejection', function(event) {
                    console.error('Unhandled promise rejection:', event.reason);
                    window.parent.postMessage({
                        type: 'error',
                        message: 'Unhandled promise rejection: ' + event.reason
                    }, '*');
                });
                
                console.log = function() {
                    const args = Array.from(arguments);
                    console.info('Iframe log:', ...args);
                    window.parent.postMessage({
                        type: 'console',
                        message: args.join(' ')
                    }, '*');
                };

                console.log('Iframe handlers initialized successfully');
            `;
            
            console.log('Evaluating script in iframe');
            iframe.contentWindow.eval(script);
            console.log('Script evaluation successful');
        } catch (e) {
            console.error('Error setting up iframe handlers:', e);
            setError('Failed to initialize content: ' + e.message);
        }
    };

    return (
        <div className="browser-viewer border rounded-lg overflow-hidden flex flex-col">
            {/* Status Bar */}
            <div className="bg-gray-100 p-2 border-b flex justify-between items-center flex-shrink-0">
                {pageInfo?.title && (
                    <div className="text-sm font-medium text-gray-600 ml-2">
                        {pageInfo.title}
                    </div>
                )}
                <div className="flex items-center gap-2">
                    <div className={`w-3 h-3 rounded-full ${
                        status === 'active' ? 'bg-green-500' :
                        status === 'closed' ? 'bg-red-500' :
                        'bg-yellow-500'  // yellow for waiting/initializing
                    }`} />
                    <span className="text-sm font-medium">
                        {status === 'waiting' && !logs.length ? 'Initializing' :
                         status === 'waiting' ? 'Loading' :
                         status === 'active' ? 'Active' :
                         'Closed'}
                    </span>
                </div>
                <span className="text-sm text-gray-600">
                    {status}
                </span>
            </div>

            {/* Browser Content */}
            <div style={{ width: 'auto', height: '768px' }}  className="inline-browser-view bg-white overflow-hidden">
                {error ? (
                    <div className="p-4 text-red-500">
                        Error: {error}
                    </div>
                ) : pageInfo && pageInfo.content ? (
                    <>
                        {console.log('Rendering iframe with:', {
                            hasContent: true,
                            contentType: typeof pageInfo.content,
                            sandboxFeatures: [
                                'allow-same-origin',
                                'allow-scripts',
                                'allow-forms',
                                'allow-popups'
                            ],
                            iframeProps: {
                                title: 'Browser Content',
                                className: 'w-full h-full border-none'
                            }
                        })}
                        <iframe
                            srcDoc={getContent()}
                            className="w-full h-full border-none"
                            sandbox="allow-same-origin allow-scripts allow-forms allow-popups"
                            title="Browser Content"
                            onLoad={handleIframeLoad}
                        />
                    </>
                ) : (
                    <div className="flex items-center justify-center h-full">
                        <div className="text-gray-500">
                            {status === 'waiting' && !logs.length ? 'Initializing browser...' :
                             status === 'waiting' ? 'Loading content...' :
                             status === 'closed' ? 'Browser is closed' :
                             'Loading...'}
                        </div>
                    </div>
                )}
            </div>

            {/* Logs Section */}
            <div className="bg-gray-50 border-t">
                {/* Tab Navigation */}
                <div className="border-b">
                    <nav className="flex justify-between items-center">
                        <div className="flex">
                        <button
                            className={`px-4 py-2 text-sm font-medium ${
                                activeTab === 'actions'
                                    ? 'border-b-2 border-blue-500 text-blue-600'
                                    : 'text-gray-500 hover:text-gray-700'
                            }`}
                            onClick={() => setActiveTab('actions')}
                        >
                            Actions
                        </button>
                        <button
                            className={`px-4 py-2 text-sm font-medium ${
                                activeTab === 'console'
                                    ? 'border-b-2 border-blue-500 text-blue-600'
                                    : 'text-gray-500 hover:text-gray-700'
                            }`}
                            onClick={() => setActiveTab('console')}
                        >
                            Console
                        </button>
                        </div>
                        <button
                            className="px-4 py-2 text-sm font-medium text-gray-500 hover:text-gray-700"
                            onClick={() => setIsLogsExpanded(!isLogsExpanded)}
                        >
                            {isLogsExpanded ? 'Collapse' : 'Expand'}
                        </button>
                    </nav>
                </div>

                {/* Log Content */}
                <div 
                    className={`overflow-y-auto transition-all duration-300 ease-in-out`}
                    style={{ height: isLogsExpanded ? '500px' : '100px' }}
                >
                    <div className="p-2">
                        {activeTab === 'actions' ? (
                            <div className="space-y-1">
                                {logs.map((log, index) => (
                                    <div 
                                        key={index}
                                        className="text-sm text-gray-600 font-mono"
                                    >
                                        {log}
                                    </div>
                                ))}
                            </div>
                        ) : (
                            <div className="space-y-1">
                                {consoleLogs.map((log, index) => (
                                    <div 
                                        key={index}
                                        className={`text-sm font-mono ${
                                            log.includes('[Error]') ? 'text-red-600' :
                                            log.includes('[Warning]') ? 'text-yellow-600' :
                                            'text-gray-600'
                                        }`}
                                    >
                                        {log}
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
}
