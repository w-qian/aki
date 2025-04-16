import { useEffect, useRef, useState } from 'react';
import { ScrollArea, ScrollBar } from "@/components/ui/scroll-area"

export default function MermaidRenderer() {
  const containerRef = useRef(null);
  const [zoomLevel, setZoomLevel] = useState(1.0);
  const [error, setError] = useState(null);
  const [svgDimensions, setSvgDimensions] = useState({ width: 0, height: 0 });
  const [isDarkTheme, setIsDarkTheme] = useState(false);
  
  // Check for dark theme preference
  useEffect(() => {
    // Check if document has a dark class or prefers-color-scheme
    const checkDarkTheme = () => {
      const hasDarkClass = document.documentElement.classList.contains('dark');
      const prefersDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
      setIsDarkTheme(hasDarkClass || prefersDark);
    };
    
    checkDarkTheme();
    
    // Listen for theme changes
    const mediaQuery = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)');
    if (mediaQuery?.addEventListener) {
      mediaQuery.addEventListener('change', checkDarkTheme);
      return () => mediaQuery.removeEventListener('change', checkDarkTheme);
    }
  }, []);
  
  // Theme colors
  const colors = {
    background: isDarkTheme ? '#1e1e2e' : '#ffffff',
    backgroundSecondary: isDarkTheme ? '#313244' : '#f1f5f9',
    border: isDarkTheme ? '#45475a' : '#e2e8f0',
    text: isDarkTheme ? '#cdd6f4' : '#1e293b',
    textSecondary: isDarkTheme ? '#bac2de' : '#475569',
    accent: isDarkTheme ? '#89b4fa' : '#3b82f6',
    error: isDarkTheme ? '#f38ba8' : '#ef4444',
  };
  
  // Style definitions
  const styles = {
    // Main container styles
    container: {
      width: '100%',
      maxWidth: '900px',
      color: colors.text
    },
    
    // Zoom controls container
    zoomControls: {
      display: 'flex',
      gap: '8px',
      marginBottom: '8px',
      justifyContent: 'flex-end'
    },
    
    // Button styles
    button: {
      background: colors.backgroundSecondary,
      border: `1px solid ${colors.border}`,
      borderRadius: '4px',
      padding: '4px 8px',
      cursor: 'pointer',
      color: colors.text
    },
    
    // Icon button variations
    iconButton: {
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center'
    },
    
    // Button icon
    buttonIcon: {
      fontSize: '16px'
    },
    
    // Diagram container
    diagramContainer: {
      width: '100%',
      border: `1px solid ${colors.border}`,
      borderRadius: '4px',
      padding: '1rem',
      position: 'relative',
      background: colors.background
    },
    
    // Scroll area
    scrollArea: {
      width: '100%',
      height: '400px',
      overflow: 'auto'
    },
    
    // Error message
    errorMessage: {
      color: colors.error,
      padding: '1rem'
    },
    
    // Content container - now dynamically sized based on SVG and zoom
    getContentContainerStyles: (svgWidth, svgHeight, zoom) => ({
      width: svgWidth * zoom > 0 ? svgWidth * zoom : 'auto',
      height: svgHeight * zoom > 0 ? svgHeight * zoom : 'auto',
      position: 'relative',
      overflow: 'visible' // Important to show all content when zoomed
    }),
    
    // SVG container
    svgContainer: {
      position: 'relative', 
      overflow: 'visible'
    }
  };
  
  // Function to handle zoom in
  const handleZoomIn = () => {
    setZoomLevel(prevZoom => Math.min(prevZoom + 0.2, 3.0)); // Max zoom 3x
  };
  
  // Function to handle zoom out
  const handleZoomOut = () => {
    setZoomLevel(prevZoom => Math.max(prevZoom - 0.2, 0.5)); // Min zoom 0.5x
  };
  
  // Function to reset zoom
  const handleResetZoom = () => {
    setZoomLevel(1.0);
  };
  
  // Function to get original SVG dimensions
  const updateSvgDimensions = () => {
    if (!containerRef.current) return;
    
    const svgElement = containerRef.current.querySelector('svg');
    if (!svgElement) return;
    
    // Get dimensions from SVG or calculate from viewBox
    let width = parseFloat(svgElement.getAttribute('width')) || 0;
    let height = parseFloat(svgElement.getAttribute('height')) || 0;
    
    // If dimensions are not set directly, try to get from viewBox
    if (width === 0 || height === 0) {
      const viewBox = svgElement.getAttribute('viewBox');
      if (viewBox) {
        const [,, vbWidth, vbHeight] = viewBox.split(' ').map(Number);
        width = vbWidth || width;
        height = vbHeight || height;
      }
    }
    
    // If we got some dimensions, save them
    if (width > 0 && height > 0) {
      // Store the original dimensions as data attributes if not already stored
      if (!svgElement.hasAttribute('data-original-width')) {
        svgElement.setAttribute('data-original-width', width);
        svgElement.setAttribute('data-original-height', height);
      }
      
      setSvgDimensions({ width, height });
    }
  };
  
  // Apply dark theme to SVG elements
  const applyThemeToSvg = () => {
    if (!containerRef.current) return;
    
    const svgElement = containerRef.current.querySelector('svg');
    if (!svgElement) return;
    
    if (isDarkTheme) {
      // Apply dark theme to SVG
      svgElement.style.filter = 'invert(0.85) hue-rotate(180deg)';
      
      // Add background fill for better visibility in dark mode
      if (!svgElement.querySelector('rect.mermaid-bg')) {
        const bg = document.createElementNS("http://www.w3.org/2000/svg", "rect");
        bg.setAttribute('width', '100%');
        bg.setAttribute('height', '100%');
        bg.setAttribute('fill', colors.background);
        bg.setAttribute('class', 'mermaid-bg');
        svgElement.insertBefore(bg, svgElement.firstChild);
      }
    } else {
      // Remove dark theme styling
      svgElement.style.filter = 'none';
      
      // Remove background if it exists
      const bg = svgElement.querySelector('rect.mermaid-bg');
      if (bg) {
        bg.remove();
      }
    }
  };
  
  // Function to apply zoom to SVG elements
  const applyZoomToSvg = () => {
    if (!containerRef.current) return;
    
    // Find the SVG element inside the container
    const svgElement = containerRef.current.querySelector('svg');
    if (!svgElement) {
      console.log('No SVG element found to zoom');
      return;
    }
    
    // Get the original dimensions
    const originalWidth = parseFloat(svgElement.getAttribute('data-original-width')) || 
                          parseFloat(svgElement.getAttribute('width')) || 
                          svgDimensions.width;
                          
    const originalHeight = parseFloat(svgElement.getAttribute('data-original-height')) || 
                           parseFloat(svgElement.getAttribute('height')) || 
                           svgDimensions.height;
    
    // Apply explicit dimensions to the SVG based on zoom
    if (originalWidth > 0) {
      const scaledWidth = originalWidth * zoomLevel;
      svgElement.setAttribute('width', scaledWidth);
    }
    
    if (originalHeight > 0) {
      const scaledHeight = originalHeight * zoomLevel;
      svgElement.setAttribute('height', scaledHeight);
    }
    
    // Scale font size for all text elements
    const textElements = svgElement.querySelectorAll('text');
    textElements.forEach(textElement => {
      const originalFontSize = textElement.getAttribute('data-original-font-size') || 
                              textElement.getAttribute('font-size') || 
                              window.getComputedStyle(textElement).fontSize;
      
      // Store original font size if not already stored
      if (!textElement.getAttribute('data-original-font-size')) {
        textElement.setAttribute('data-original-font-size', originalFontSize);
      }
      
      // Extract the numeric part of the font size
      const fontSize = parseFloat(originalFontSize);
      if (!isNaN(fontSize)) {
        const scaledFontSize = fontSize * zoomLevel;
        textElement.setAttribute('font-size', `${scaledFontSize}px`);
      }
    });
    
    // Also scale other elements that might contain text or have size attributes
    const scalableElements = svgElement.querySelectorAll('rect, circle, ellipse, line, polyline, polygon, path');
    scalableElements.forEach(element => {
      // Store original stroke-width if not already stored
      const originalStrokeWidth = element.getAttribute('data-original-stroke-width') || 
                                 element.getAttribute('stroke-width');
                                 
      if (originalStrokeWidth && !element.getAttribute('data-original-stroke-width')) {
        element.setAttribute('data-original-stroke-width', originalStrokeWidth);
      }
      
      // Scale stroke-width if present
      if (originalStrokeWidth) {
        const strokeWidth = parseFloat(originalStrokeWidth);
        if (!isNaN(strokeWidth)) {
          const scaledStrokeWidth = strokeWidth * zoomLevel;
          element.setAttribute('stroke-width', scaledStrokeWidth);
        }
      }
    });
  };
  
  // Function to render mermaid diagram
  useEffect(() => {
    if (!containerRef.current) {
      console.log('Container ref is null');
      return;
    }
    
    // Access mermaid code from global variable if it exists
    // This looks for mermaidCode in multiple possible places
    const mermaidCode = window.mermaidCode || 
                        (window.props && window.props.mermaidCode) || 
                        (typeof props !== 'undefined' && props && props.mermaidCode);
    
    if (!mermaidCode) {
      console.log('Looking for mermaid code in global context');
      // Try to find the mermaid code from the component's context
      const diagramElements = document.getElementsByClassName('mermaid');
      if (diagramElements.length > 0) {
        // Use content from an existing mermaid element if found
        const existingMermaidCode = diagramElements[0].textContent;
        if (existingMermaidCode) {
          console.log('Found mermaid code in DOM element');
          renderWithCode(existingMermaidCode);
          return;
        }
      }
      
      setError('No mermaid code found. Please check component implementation.');
      return;
    }

    renderWithCode(mermaidCode);
  }, []);

  // Apply zoom when zoom level changes
  useEffect(() => {
    applyZoomToSvg();
  }, [zoomLevel]);
  
  // Apply theme changes when theme changes
  useEffect(() => {
    applyThemeToSvg();
  }, [isDarkTheme]);

  // Function to render with provided code
  const renderWithCode = (code) => {
    console.log('Attempting to render mermaid diagram');

    // Clear previous content and errors
    containerRef.current.innerHTML = '';
    setError(null);

    // Check if mermaid is already loaded
    if (window.mermaid) {
      renderDiagram(window.mermaid, code);
    } else {
      // Dynamically load mermaid library
      const script = document.createElement('script');
      script.src = 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js';
      script.async = true;
      
      script.onload = () => {
        console.log('Mermaid script loaded');
        renderDiagram(window.mermaid, code);
      };
      
      script.onerror = (e) => {
        console.error('Failed to load mermaid script:', e);
        setError('Failed to load mermaid library');
      };
      
      document.body.appendChild(script);
    }
  };

  // Function to actually render the diagram
  const renderDiagram = (mermaid, code) => {
    try {
      console.log('Configuring mermaid');
      // Configure mermaid
      mermaid.initialize({
        startOnLoad: false,  // We'll manually initialize
        theme: isDarkTheme ? 'dark' : 'default',
        securityLevel: 'loose',
      });
      
      // Create a container for the diagram
      const diagramContainer = document.createElement('div');
      diagramContainer.className = 'mermaid';
      diagramContainer.textContent = code;
      containerRef.current.appendChild(diagramContainer);
      
      console.log('Initializing mermaid diagram');
      mermaid.init(undefined, diagramContainer);
      console.log('Mermaid initialization complete');
      
      // Get SVG dimensions after rendering
      setTimeout(() => {
        updateSvgDimensions();
        applyZoomToSvg();
        applyThemeToSvg();
      }, 100);
    } catch (err) {
      console.error('Mermaid rendering error:', err);
      setError(`Mermaid rendering error: ${err.message}`);
    }
  };

  return (
    <div className="mermaid-renderer-container" style={styles.container}>
      {/* Zoom controls */}
      <div className="zoom-controls" style={styles.zoomControls}>
        <button 
          onClick={handleZoomOut}
          style={{...styles.button, ...styles.iconButton}}
          aria-label="Zoom out"
        >
          <span style={styles.buttonIcon}>-</span>
        </button>
        
        <button 
          onClick={handleResetZoom}
          style={styles.button}
          aria-label="Reset zoom"
        >
          {Math.round(zoomLevel * 100)}%
        </button>
        
        <button 
          onClick={handleZoomIn}
          style={{...styles.button, ...styles.iconButton}}
          aria-label="Zoom in"
        >
          <span style={styles.buttonIcon}>+</span>
        </button>
      </div>
      
      {/* Scrollable diagram area */}
      <div style={styles.diagramContainer}>
        <ScrollArea style={styles.scrollArea}>
          {/* Error message if rendering fails */}
          {error && (
            <div style={styles.errorMessage}>
              {error}
            </div>
          )}
          
          {/* Dynamic content container based on SVG dimensions and zoom */}
          <div style={styles.getContentContainerStyles(svgDimensions.width, svgDimensions.height, zoomLevel)}>
            <div ref={containerRef} style={styles.svgContainer} />
          </div>
          <ScrollBar orientation="horizontal" />
        </ScrollArea>
      </div>
    </div>
  );
}