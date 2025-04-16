import { useEffect, useRef, useState } from 'react';
import { ScrollArea, ScrollBar } from "@/components/ui/scroll-area"

export default function MermaidRenderer() {
  const containerRef = useRef(null);
  const [zoomLevel, setZoomLevel] = useState(1.0);
  const [error, setError] = useState(null);
  
  // Style definitions
  const styles = {
    // Main container styles
    container: {
      width: '100%',
      maxWidth: '900px'
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
      background: '#f1f5f9',
      border: '1px solid #cbd5e1',
      borderRadius: '4px',
      padding: '4px 8px',
      cursor: 'pointer'
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
      border: '1px solid #e2e8f0',
      borderRadius: '4px',
      padding: '1rem',
      position: 'relative'
    },
    
    // Scroll area
    scrollArea: {
      width: '100%',
      height: '100%',
      overflow: 'auto'
    },
    
    // Error message
    errorMessage: {
      color: 'red',
      padding: '1rem'
    },
    
    // Dynamic styles based on zoom level
    getDiagramStyles: (zoom) => ({
      transform: `scale(${zoom})`,
      transformOrigin: 'top left',
      width: 'max-content',
      minWidth: '100%'
    })
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
  }, [zoomLevel]);

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
        theme: 'default',
        securityLevel: 'loose',
      });
      
      // Create a container for the diagram
      const diagramContainer = document.createElement('div');
      diagramContainer.className = 'mermaid';
      diagramContainer.textContent = code;
      containerRef.current.appendChild(diagramContainer);
      
      mermaid.init(undefined, diagramContainer);
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
          
          {/* Diagram container */}
          <div style={styles.getDiagramStyles(zoomLevel)}>
            <div ref={containerRef} />
          </div>
          <ScrollBar orientation="horizontal" />
        </ScrollArea>
      </div>
    </div>
  );
}