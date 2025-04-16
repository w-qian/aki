import { useEffect, useRef, useState } from 'react';
import { Button } from '@/components/ui/button';
import { ZoomIn, ZoomOut, Maximize, X } from 'lucide-react';

export default function MermaidRenderer() {
  const containerRef = useRef(null);
  const [error, setError] = useState(null);
  const [zoom, setZoom] = useState(1);
  const [isPopup, setIsPopup] = useState(false);
  
  // Function to render mermaid diagram
  useEffect(() => {
    if (!containerRef.current || !props.mermaidCode) return;

    // Dynamically load mermaid library
    const script = document.createElement('script');
    script.src = 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js';
    script.async = true;
    
    script.onload = () => {
      const mermaid = window.mermaid;
      
      // Configure mermaid
      mermaid.initialize({
        startOnLoad: false,  // We'll manually initialize
        theme: 'default',
        securityLevel: 'loose',
      });
      
      try {
        // Clear previous content
        containerRef.current.innerHTML = '';
        
        // Create a container for the diagram
        const diagramContainer = document.createElement('div');
        diagramContainer.className = 'mermaid';
        diagramContainer.textContent = props.mermaidCode;
        containerRef.current.appendChild(diagramContainer);
        
        // Use the parseError callback to catch syntax errors
        const renderResult = mermaid.parse(props.mermaidCode);
        if (!renderResult) {
          // If parse returned false, check for syntax errors
          mermaid.init(undefined, diagramContainer)
            .catch(err => {
              console.error('Mermaid parsing error:', err);
              // Return error to parent tool
              updateElement({ syntaxError: err.message || 'Syntax error in diagram' });
              setError(`Syntax error in diagram: ${err.message || 'Invalid mermaid syntax'}`);
            });
        } else {
          // If no parse errors, render normally
          mermaid.init(undefined, diagramContainer);
          setError(null);
        }
      } catch (err) {
        console.error('Mermaid rendering error:', err);
        // Return error to parent tool
        updateElement({ syntaxError: err.message || 'Error rendering diagram' });
        setError(`Error rendering diagram: ${err.message || 'Unknown error'}`);
      }
    };
    
    script.onerror = () => {
      setError('Failed to load mermaid library');
      // Return error to parent tool
      updateElement({ syntaxError: 'Failed to load mermaid library' });
    };
    
    document.body.appendChild(script);
    
    return () => {
      if (document.body.contains(script)) {
        document.body.removeChild(script);
      }
    };
  }, [props.mermaidCode]);

  // Zoom in function
  const zoomIn = () => {
    setZoom(prevZoom => Math.min(prevZoom + 0.2, 3));
  };

  // Zoom out function
  const zoomOut = () => {
    setZoom(prevZoom => Math.max(prevZoom - 0.2, 0.5));
  };

  // Toggle popup
  const togglePopup = () => {
    setIsPopup(!isPopup);
  };

  if (error) {
    return (
      <div className="p-4 border border-red-300 bg-red-50 text-red-700 rounded">
        <h3 className="font-semibold mb-2">Mermaid Diagram Error</h3>
        <pre className="whitespace-pre-wrap text-sm">{error}</pre>
      </div>
    );
  }

  const diagramStyles = {
    transform: `scale(${zoom})`,
    transformOrigin: 'top left',
    transition: 'transform 0.2s ease-in-out',
  };

  // Use 75% of screen instead of full screen for popup
  const popupStyles = isPopup ? {
    position: 'fixed',
    top: '12.5%',
    left: '12.5%',
    width: '75%',
    height: '75%',
    zIndex: 50,
    backgroundColor: 'white',
    borderRadius: '8px',
    boxShadow: '0 10px 25px rgba(0, 0, 0, 0.1)',
    overflow: 'auto',
    padding: '1rem',
  } : {};

  return (
    <div>
      <div className="flex gap-2 mb-2">
        <Button variant="outline" size="sm" onClick={zoomIn}>
          <ZoomIn className="h-4 w-4 mr-1" /> Zoom In
        </Button>
        <Button variant="outline" size="sm" onClick={zoomOut}>
          <ZoomOut className="h-4 w-4 mr-1" /> Zoom Out
        </Button>
        <Button variant="outline" size="sm" onClick={togglePopup}>
          <Maximize className="h-4 w-4 mr-1" /> {isPopup ? 'Exit Enlarged View' : 'Enlarge'}
        </Button>
      </div>
      
      {/* Render main or popup view */}
      {isPopup ? (
        <div style={popupStyles}>
          <div className="flex justify-between items-center mb-3 border-b pb-2">
            <h3 className="font-medium">Mermaid Diagram</h3>
            <Button variant="ghost" size="sm" onClick={togglePopup}>
              <X className="h-4 w-4" />
            </Button>
          </div>
          <div 
            ref={containerRef} 
            className="mermaid-container" 
            style={diagramStyles}
          ></div>
        </div>
      ) : (
        <div className="bg-white border border-gray-200 rounded-md overflow-auto p-4">
          <div 
            ref={containerRef} 
            className="mermaid-container" 
            style={diagramStyles}
          ></div>
        </div>
      )}
    </div>
  );
}