function updateVisualization(data) {
    if (!data || !data.nodes || !data.links) {
        console.warn('Invalid topology data received');
        return;
    }

    // Clear previous visualization
    g.selectAll('*').remove();

    const masterNode = data.nodes.find(n => n.role === 'master');
    const workerNodes = data.nodes.filter(n => n.role !== 'master');

    // Set up dimensions
    const centerX = width / 2;
    const masterY = height * 0.2;  // Master at top 20%
    const workerY = height * 0.6;  // Workers at 60% down
    
    // Create master node
    if (masterNode) {
        const masterGroup = g.append('g')
            .attr('class', 'node master')
            .attr('transform', `translate(${centerX}, ${masterY})`);

        // Add master label
        masterGroup.append('text')
            .attr('class', 'node-type-label')
            .attr('y', -40)
            .attr('text-anchor', 'middle')
            .text('MASTER NODE')
            .style('font-size', '16px');

        createNodeBox.call(masterGroup.node(), masterNode);
    }

    // Position worker nodes horizontally
    const workerSpacing = Math.min(width * 0.2, 400); // Adaptive spacing
    const totalWidth = (workerNodes.length - 1) * workerSpacing;
    const startX = centerX - totalWidth / 2;

    workerNodes.forEach((node, i) => {
        const x = startX + (i * workerSpacing);
        const workerGroup = g.append('g')
            .attr('class', 'node worker')
            .attr('transform', `translate(${x}, ${workerY})`);

        // Add worker label
        workerGroup.append('text')
            .attr('class', 'node-type-label')
            .attr('y', -40)
            .attr('text-anchor', 'middle')
            .text(`WORKER NODE ${i + 1}`)
            .style('font-size', '16px');

        createNodeBox.call(workerGroup.node(), node);

        // Create connection to master
        if (masterNode) {
            const linkGroup = g.append('g')
                .attr('class', 'link-group');

            const startPoint = { x: centerX, y: masterY + 100 }; // Bottom of master
            const endPoint = { x: x, y: workerY - 100 }; // Top of worker
            
            // Draw main connection line
            const linePath = linkGroup.append('g');
            
            // Create dotted line effect
            const distance = Math.sqrt(Math.pow(endPoint.x - startPoint.x, 2) + Math.pow(endPoint.y - startPoint.y, 2));
            const dots = Math.floor(distance / 15); // One dot every 15 pixels
            
            for (let j = 0; j <= dots; j++) {
                const t = j / dots;
                const dotX = startPoint.x + (endPoint.x - startPoint.x) * t;
                const dotY = startPoint.y + (endPoint.y - startPoint.y) * t;
                
                linePath.append('text')
                    .attr('x', dotX)
                    .attr('y', dotY)
                    .attr('class', 'connection-dot')
                    .attr('text-anchor', 'middle')
                    .text('·')
                    .style('animation', `blink ${1 + Math.random()}s infinite`);
            }

            // Add connection status
            const midX = (startPoint.x + endPoint.x) / 2;
            const midY = (startPoint.y + endPoint.y) / 2;

            linkGroup.append('text')
                .attr('x', midX)
                .attr('y', midY)
                .attr('class', 'connection-status')
                .attr('text-anchor', 'middle')
                .text('↔ CONNECTED ↔')
                .style('animation', 'pulse 2s infinite');
        }
    });

    // Add these styles
    const newStyles = `
        .node-type-label {
            fill: #33ff33;
            font-family: 'Courier New', monospace;
            font-weight: bold;
        }
        .connection-dot {
            fill: #33ff33;
            font-size: 24px;
        }
        .connection-status {
            fill: #33ff33;
            font-family: 'Courier New', monospace;
            font-size: 12px;
        }
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
    `;

    // Update styles
    const styleSheet = document.createElement('style');
    styleSheet.textContent = styles + newStyles;
    document.head.appendChild(styleSheet);

    // Update stats
    updateStats(data);
}