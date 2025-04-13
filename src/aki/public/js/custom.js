// Browser viewer utilities
window.BrowserViewer = {
    // Initialize browser viewer
    init() {
        console.log('Browser viewer initialized');
        this.setupMessageHandling();
    },

    // Setup message handling for iframe communication
    setupMessageHandling() {
        window.addEventListener('message', (event) => {
            // Only handle messages from our iframes
            if (!event.source.frameElement) return;
            
            try {
                const data = event.data;
                if (data.type === 'console') {
                    console.log('[Browser Console]:', data.message);
                } else if (data.type === 'error') {
                    console.error('[Browser Error]:', data.message);
                }
            } catch (e) {
                console.error('Error handling iframe message:', e);
            }
        });
    },

    // Utility function to safely parse HTML content
    parseContent(content) {
        try {
            return content
                .replace(/\\"/g, '"')
                .replace(/\\n/g, '\n')
                .replace(/\\t/g, '\t')
                .replace(/\\r/g, '\r');
        } catch (e) {
            console.error('Error parsing content:', e);
            return content;
        }
    }
};

// Initialize on page load
window.addEventListener('load', () => {
    window.BrowserViewer.init();
});
