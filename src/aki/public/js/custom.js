/**
 * Mermaid Diagram Renderer with Zoom Functionality
 * 
 * This script:
 * 1. Renders Mermaid code blocks as actual diagrams
 * 2. Adds zoom in/out functionality to the rendered diagrams
 */

// Load required libraries
document.addEventListener('DOMContentLoaded', function() {
  // Load Mermaid.js library if not already present
  if (!window.mermaid) {
    const mermaidScript = document.createElement('script');
    mermaidScript.src = 'https://cdn.jsdelivr.net/npm/mermaid@10.6.1/dist/mermaid.min.js';
    mermaidScript.async = true;
    document.head.appendChild(mermaidScript);
    
    mermaidScript.onload = function() {
      initializeMermaid();
      loadSvgPanZoom();
    };
  } else {
    initializeMermaid();
    loadSvgPanZoom();
  }
});

/**
 * Load SVG Pan Zoom library
 */
function loadSvgPanZoom() {
  // Add SVG Pan Zoom library if not already loaded
  if (!window.svgPanZoom) {
    const svgPanZoomScript = document.createElement('script');
    svgPanZoomScript.src = 'https://cdn.jsdelivr.net/npm/svg-pan-zoom@3.6.1/dist/svg-pan-zoom.min.js';
    svgPanZoomScript.async = true;
    document.head.appendChild(svgPanZoomScript);
    
    svgPanZoomScript.onload = function() {
      addMermaidZoomStyles();
      setupMermaidObserver();
    };
  } else {
    addMermaidZoomStyles();
    setupMermaidObserver();
  }
}

/**
 * Initialize Mermaid library
 */
function initializeMermaid() {
  if (window.mermaid) {
    // Configure Mermaid
    window.mermaid.initialize({
      startOnLoad: true,
      theme: 'default',
      securityLevel: 'loose', // Required for some interactive features
      fontFamily: 'Arial, sans-serif',
      fontSize: 18, // Increased base font size for better readability
      logLevel: 3, // Error by default to avoid console spam
      flowchart: {
        htmlLabels: true,
        useMaxWidth: false, // Allow full-width rendering
        curve: 'linear', // Smoother curves
        diagramPadding: 10 // Add some padding
      },
      gantt: {
        useMaxWidth: false,
        fontSize: 16 // Specific font size for gantt charts
      },
      sequence: {
        useMaxWidth: false,
        boxMargin: 10, // Better spacing
        mirrorActors: false, // Don't duplicate actors at bottom
        actorMargin: 120, // More space between actors
        messageMargin: 40 // More space for messages
      }
    });
    
    // Render existing mermaid code blocks
    renderMermaidBlocks();
  } else {
    console.warn('Mermaid library not loaded yet');
  }
}

/**
 * Check if mermaid syntax appears to be complete enough to render
 * @param {string} content - The mermaid code to check
 * @returns {boolean} - Whether the syntax looks renderable
 */
function isMermaidSyntaxComplete(content) {
  if (!content || content.trim().length < 10) return false;
  
  // Check for common mermaid syntax patterns that indicate completeness
  const hasEndMarker = /\b(?:end|}\s*$)/.test(content);
  const hasDefinedStructure = /\b(?:graph|flowchart|sequenceDiagram|classDiagram|stateDiagram|gantt|pie|journey)\b/.test(content);
  
  // Need at least a diagram type marker
  return hasDefinedStructure;
}

/**
 * Estimate diagram complexity to determine appropriate size class
 * @param {string} content - The mermaid code to analyze
 * @returns {string} - Size class (small-diagram, medium-diagram, or large-diagram)
 */
function estimateDiagramComplexity(content) {
  if (!content) return 'small-diagram';
  
  // Count nodes and edges by looking for common patterns
  const lines = content.trim().split('\n').length;
  const nodes = (content.match(/\b[A-Za-z0-9_]+\b\s*(\[|\(|{|:)/g) || []).length;
  const connections = (content.match(/(-+>|--+|==+|\.\.+)/g) || []).length;
  const complexity = lines + nodes + connections;
  
  if (complexity < 10) {
    return 'small-diagram';
  } else if (complexity < 25) {
    return 'medium-diagram'; 
  } else {
    return 'large-diagram';
  }
}

/**
 * Create and show popup with the mermaid diagram
 * @param {Element} container - The mermaid container element
 * @param {Element} svg - The SVG element to display in popup
 */
function showMermaidPopup(container, svg) {
  // Create overlay
  const overlay = document.createElement('div');
  overlay.className = 'mermaid-popup-overlay';
  
  // Create popup content
  const popupContent = document.createElement('div');
  popupContent.className = 'mermaid-popup-content';
  
  // Create a container div for the SVG to ensure proper centering
  const svgContainer = document.createElement('div');
  svgContainer.style.width = '100%';
  svgContainer.style.height = '100%';
  svgContainer.style.display = 'flex';
  svgContainer.style.alignItems = 'center';
  svgContainer.style.justifyContent = 'center';
  
  // Clone the SVG for the popup
  const clonedSvg = svg.cloneNode(true);
  clonedSvg.style.width = 'auto';
  clonedSvg.style.height = 'auto';
  clonedSvg.style.maxWidth = '100%';
  clonedSvg.style.maxHeight = '85vh'; /* Use viewport height for better scaling */
  clonedSvg.style.margin = '0'; /* Reset margin */
  clonedSvg.style.display = 'block'; /* Ensure block display */
  
  // Add the SVG to its container
  svgContainer.appendChild(clonedSvg);
  
  // Add close button
  const closeBtn = document.createElement('div');
  closeBtn.className = 'mermaid-popup-close';
  closeBtn.innerHTML = '\u00d7';
  closeBtn.title = 'Close';
  closeBtn.addEventListener('click', function() {
    document.body.removeChild(overlay);
  });
  
  // Add escape key handler
  const escHandler = function(e) {
    if (e.key === 'Escape') {
      document.body.removeChild(overlay);
      document.removeEventListener('keydown', escHandler);
    }
  };
  document.addEventListener('keydown', escHandler);
  
  // Assemble popup
  popupContent.appendChild(closeBtn);
  popupContent.appendChild(svgContainer); // Add the container instead of directly adding SVG
  overlay.appendChild(popupContent);
  document.body.appendChild(overlay);
  
  // Center the diagram after adding to DOM
  setTimeout(() => {
    if (window.svgPanZoom && clonedSvg) {
      try {
        const panZoomInstance = window.svgPanZoom(clonedSvg, {
          zoomEnabled: true,
          controlIconsEnabled: false,
          fit: true,
          center: true,
          minZoom: 0.5
        });
        
        // Force a fit/center operation after rendering
        panZoomInstance.resize();
        panZoomInstance.fit();
        panZoomInstance.center();
      } catch (error) {
        console.warn('Could not initialize SVG pan-zoom in popup', error);
      }
    }
  }, 100);
  
  // Also close when clicking the overlay background (but not popup content)
  overlay.addEventListener('click', function(e) {
    if (e.target === overlay) {
      document.body.removeChild(overlay);
    }
  });
}

/**
 * Find and render Mermaid code blocks
 */
function renderMermaidBlocks() {
  // Find all pre > code.language-mermaid elements (standard markdown format)
  document.querySelectorAll('pre > code.language-mermaid').forEach(codeElement => {
    const preElement = codeElement.parentElement;
    const content = codeElement.textContent;
    
    // Skip if mermaid content doesn't look complete enough to render
    if (!isMermaidSyntaxComplete(content)) {
      return;
    }
    
    // Create a div to hold the rendered diagram
    const mermaidDiv = document.createElement('div');
    mermaidDiv.className = 'mermaid';
    mermaidDiv.textContent = content;
    
    // Apply size classification based on complexity
    const complexityClass = estimateDiagramComplexity(content);
    mermaidDiv.classList.add(complexityClass);
    
    // Replace the pre element with the mermaid div
    preElement.parentNode.replaceChild(mermaidDiv, preElement);
  });
  
  // Also handle any elements with class 'mermaid' that aren't yet rendered
  if (window.mermaid) {
    try {
      window.mermaid.run();
      // After rendering, apply zoom functionality
      setTimeout(() => {
        document.querySelectorAll('.mermaid svg').forEach(applySvgPanZoom);
      }, 300);
    } catch (error) {
      console.error('Error rendering Mermaid diagrams:', error);
      
      // Try to find and mark problematic diagrams so we don't keep retrying them
      document.querySelectorAll('.mermaid:not(:has(svg))').forEach(div => {
        if (!div.classList.contains('mermaid-error') && div.textContent.trim().length > 0) {
          // Only mark as error if it's been attempted before
          if (div.getAttribute('data-render-attempted') === 'true') {
            div.classList.add('mermaid-error');
            
            // Add a small indicator this diagram has syntax errors
            const errorNote = document.createElement('div');
            errorNote.className = 'mermaid-error-note';
            errorNote.textContent = 'Diagram syntax is being generated...';
            errorNote.style.color = '#e74c3c';
            errorNote.style.fontSize = '12px';
            errorNote.style.padding = '8px';
            div.prepend(errorNote);
          } else {
            // Mark that we've attempted to render this diagram
            div.setAttribute('data-render-attempted', 'true');
          }
        }
      });
    }
  }
}

/**
 * Add custom styles for the zoom controls
 */
function addMermaidZoomStyles() {
  if (document.getElementById('mermaid-zoom-styles')) {
    return; // Already added
  }
  
  // Load external stylesheet
  const link = document.createElement('link');
  link.id = 'mermaid-zoom-styles';
  link.rel = 'stylesheet';
  link.href = '/css/stylesheet.css';
  document.head.appendChild(link);
}

/**
 * Apply SVG Pan Zoom functionality to a Mermaid SVG
 * @param {Element} svg - The SVG element to enhance
 */
function applySvgPanZoom(svg) {
  // Skip if already enhanced or not a valid SVG
  if (!svg || svg.getAttribute('data-pan-zoom-applied') === 'true') {
    return;
  }
  
  // Make sure the parent container is positioned
  const container = svg.closest('.mermaid');
  if (!container) return;
  
  // Determine diagram complexity and set appropriate class if not already set
  if (!container.classList.contains('small-diagram') && 
      !container.classList.contains('medium-diagram') &&
      !container.classList.contains('large-diagram')) {
    const content = container.textContent || '';
    const complexityClass = estimateDiagramComplexity(content);
    container.classList.add(complexityClass);
  }
  
  container.style.position = 'relative';
  
  // Create zoom controls container
  const controlsContainer = document.createElement('div');
  controlsContainer.className = 'zoom-controls';
  
  // Create expand button for popup view (placed in zoom controls)
  const expandBtn = document.createElement('button');
  expandBtn.className = 'expand-button';
  expandBtn.innerHTML = '\u26f6'; // Expand symbol
  expandBtn.title = 'Open in popup';
  expandBtn.addEventListener('click', function(e) {
    e.stopPropagation();
    showMermaidPopup(container, svg);
  });
  
  // Create zoom in button
  const zoomInBtn = document.createElement('button');
  zoomInBtn.innerHTML = '+'; // Simple plus sign
  zoomInBtn.title = 'Zoom in';
  
  // Create zoom out button
  const zoomOutBtn = document.createElement('button');
  zoomOutBtn.innerHTML = '-'; // Simple minus sign
  zoomOutBtn.title = 'Zoom out';
  
  // Create reset button
  const resetBtn = document.createElement('button');
  resetBtn.innerHTML = '\u21ba'; // Reset symbol
  resetBtn.title = 'Reset zoom';
  
  // Add buttons to container in desired order
  controlsContainer.appendChild(expandBtn); // Add expand button first
  controlsContainer.appendChild(zoomInBtn);
  controlsContainer.appendChild(zoomOutBtn);
  controlsContainer.appendChild(resetBtn);
  
  // Add container to diagram
  container.appendChild(controlsContainer);
  
  // Make sure SVG has proper dimensions
  if (!svg.getAttribute('width')) svg.setAttribute('width', '100%');
  if (!svg.getAttribute('height')) svg.setAttribute('height', '100%');
  
  // Initialize svg-pan-zoom if library is loaded
  if (window.svgPanZoom) {
    try {
      const panZoomInstance = svgPanZoom(svg, {
        zoomEnabled: true,
        controlIconsEnabled: false,
        fit: true,
        center: true,
        minZoom: 0.5,
        maxZoom: 10,
        zoomScaleSensitivity: 0.3,
        eventsHandler: {
          // Customize SVG pan/zoom behavior for smoother interaction
          haltEventListeners: ['touchstart', 'touchend', 'touchmove', 'touchleave', 'touchcancel'],
          init: function(options) {
            return {
              options: options
            };
          },
          refresh: function() {},
          destroy: function() {}
        }
      });
      
      // Add event listeners to buttons
      zoomInBtn.addEventListener('click', function(e) {
        panZoomInstance.zoomIn();
        e.stopPropagation(); // Prevent click from propagating
      });
      
      zoomOutBtn.addEventListener('click', function(e) {
        panZoomInstance.zoomOut();
        e.stopPropagation();
      });
      
      resetBtn.addEventListener('click', function(e) {
        panZoomInstance.reset();
        e.stopPropagation();
      });
      
      // Mark as enhanced
      svg.setAttribute('data-pan-zoom-applied', 'true');
    } catch (error) {
      console.error('Error applying SVG pan-zoom:', error);
    }
  } else {
    console.warn('SVG Pan Zoom library not loaded yet');
  }
}

/**
 * Set up a mutation observer to detect when new content is added
 */
function setupMermaidObserver() {
  // Create a mutation observer
  const observer = new MutationObserver(function(mutations) {
    let contentAdded = false;
    
    mutations.forEach(function(mutation) {
      if (mutation.addedNodes.length) {
        contentAdded = true;
      }
    });
    
    // If content was added, check for new code blocks and diagrams
    if (contentAdded) {
      renderMermaidBlocks();
      
      // Also check for any diagrams that might have been directly rendered
      setTimeout(() => {
        document.querySelectorAll('.mermaid svg:not([data-pan-zoom-applied="true"])').forEach(applySvgPanZoom);
      }, 300);
    }
  });
  
  // Start observing the entire document body
  observer.observe(document.body, {
    childList: true,
    subtree: true
  });
  
  // Initial rendering and zoom application
  renderMermaidBlocks();
  
  // Debounce function to prevent too frequent rendering
  let mermaidRenderTimer = null;
  let lastMermaidContent = {};
  let contentStableCount = {};
  
  // Function to debounce mermaid rendering with adaptive timing
  function debouncedRenderMermaid() {
    clearTimeout(mermaidRenderTimer);
    mermaidRenderTimer = setTimeout(() => {
      renderMermaidBlocks();
    }, 1000); // 1000ms debounce time - longer to allow more content to arrive
  }
  
  // Intelligently check for diagram updates with content stability tracking
  setInterval(() => {
    // Check unrendered code blocks
    const unrenderedBlocks = document.querySelectorAll('pre > code.language-mermaid');
    let hasChangingContent = false;
    
    unrenderedBlocks.forEach((block, index) => {
      const content = block.textContent;
      const key = `unrendered-${index}`;
      
      // Initialize if needed
      if (!contentStableCount[key]) {
        contentStableCount[key] = 0;
      }
      
      // If content has changed or is new
      if (lastMermaidContent[key] !== content) {
        lastMermaidContent[key] = content;
        contentStableCount[key] = 0; // Reset stability counter
        hasChangingContent = true;
      } else {
        // Content hasn't changed, increment stability counter
        contentStableCount[key]++;
      }
      
      // If content has been stable for a while and looks renderable, render it
      if (contentStableCount[key] >= 2 && isMermaidSyntaxComplete(content)) {
        debouncedRenderMermaid();
      }
    });
    
    // Check for incomplete rendered diagrams
    const incompleteRenderedDiagrams = document.querySelectorAll('.mermaid:not(:has(svg)):not(.mermaid-error)');
    
    // Clear error status from diagrams with errors periodically to allow re-rendering
    document.querySelectorAll('.mermaid.mermaid-error').forEach(div => {
      // Only retry rendering every ~10 seconds to avoid constant attempts
      if (Math.random() < 0.1) { // 10% chance each check (~every 10 seconds on average)
        div.classList.remove('mermaid-error');
        div.removeAttribute('data-render-attempted');
        const errorNote = div.querySelector('.mermaid-error-note');
        if (errorNote) errorNote.remove();
        hasChangingContent = true;
      }
    });
    
    // If no changes detected, try rendering incomplete diagrams periodically
    if (!hasChangingContent && incompleteRenderedDiagrams.length > 0) {
      debouncedRenderMermaid();
    }
  }, 1000);
}