import React, { useEffect, useRef } from 'react';

export default function HtmlRenderer() {
    const iframeRef = useRef(null);

    useEffect(() => {
        if (!iframeRef.current || !props.html) return;
        
        const iframe = iframeRef.current;
        const doc = iframe.contentDocument;
        
        // Write the HTML content to the iframe
        doc.open();
        doc.write(props.html);
        doc.close();

        // Adjust iframe height to content
        const resizeObserver = new ResizeObserver(() => {
            const height = doc.documentElement.scrollHeight;
            iframe.style.height = height + 'px';
        });
        
        resizeObserver.observe(doc.documentElement);
        
        return () => resizeObserver.disconnect();
    }, [props.html]);

    return (
        <iframe 
            ref={iframeRef}
            className="w-full border-none"
            title="HTML Content"
        />
    );
}
