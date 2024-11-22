// topology.js
(function() {
    // Initialize D3 visualization
    const width = window.innerWidth;
    const height = window.innerHeight;

    const svg = d3.select('#topology')
        .append('svg')
        .attr('width', width)
        .attr('height', height);

    // Add zoom behavior
    const g = svg.append('g');
    const zoom = d3.zoom()
        .scaleExtent([0.1, 4])
        .on('zoom', (event) => {
            g.attr('transform', event.transform);
        });
    svg.call(zoom);

    // Set up WebSocket connection
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${wsProtocol}//${window.location.hostname}:${window.location.port}/ws`;
    console.log('Connecting to WebSocket:', wsUrl);

    let ws = null;
    let reconnectAttempts = 0;
    const maxReconnectAttempts = 5;

    function connectWebSocket() {
        ws = new WebSocket(wsUrl);
        console.log('Creating new WebSocket connection...');

        ws.onopen = () => {
            console.log('WebSocket connected successfully');
            reconnectAttempts = 0;
            d3.select('.connection-status')
                .style('color', '#4CAF50')
                .text('● Connected to server');
        };

        ws.onclose = () => {
            console.log('WebSocket disconnected');
            d3.select('.connection-status')
                .style('color', '#ff4444')
                .text('● Disconnected from server');
            
            if (reconnectAttempts < maxReconnectAttempts) {
                reconnectAttempts++;
                console.log(`Attempting to reconnect (${reconnectAttempts}/${maxReconnectAttempts})...`);
                setTimeout(connectWebSocket, 2000);
            }
        };

        ws.onerror = (error) => {
            console.error('WebSocket error:', error);
        };

        ws.onmessage = (event) => {
            console.log('Received message:', event.data);
            try {
                const data = JSON.parse(event.data);
                if (data.nodes && data.links) {
                    console.log('Updating visualization with:', data);
                    updateVisualization(data);
                }
            } catch (e) {
                console.error('Error processing message:', e);
            }
        };
    }

    // Add to the top of the file, after the initial const declarations
    const COLORS = {
        master: '#00ff44',
        worker: '#00ccff',
        text: '#e0ffe0',
        border: '#33ff33',
        background: 'rgba(0, 20, 0, 0.7)',
        link: '#00ff4455',
        glow: {
            master: '#00ff4455',
            worker: '#00ccff55'
        }
    };

    // Add this new function for better initial node positioning
    function initialNodePositions(nodes, width, height) {
        const centerX = width / 2;
        const centerY = height / 2;
        const radius = Math.min(width, height) / 4;

        // Position master node in center
        const masterNode = nodes.find(n => n.role === 'master');
        if (masterNode) {
            masterNode.x = centerX;
            masterNode.y = centerY;
        }

        // Position worker nodes in a circle around master
        const workerNodes = nodes.filter(n => n.role === 'worker');
        workerNodes.forEach((node, i) => {
            const angle = (2 * Math.PI * i) / workerNodes.length;
            node.x = centerX + radius * Math.cos(angle);
            node.y = centerY + radius * Math.sin(angle);
        });
    }

    // Update the visualization function
    function updateVisualization(data) {
        if (!data || !data.nodes || !data.links) {
            console.warn('Invalid topology data received');
            return;
        }

        // Clear previous visualization
        g.selectAll('*').remove();

        // Initialize node positions
        initialNodePositions(data.nodes, width, height);

        // Update simulation with better forces
        const simulation = d3.forceSimulation(data.nodes)
            .force('link', d3.forceLink(data.links).id(d => d.id).distance(300))
            .force('charge', d3.forceManyBody().strength(-1000))
            .force('center', d3.forceCenter(width / 2, height / 2))
            .force('collision', d3.forceCollide().radius(d => Math.sqrt(d.nodeWidth * d.nodeHeight) / 1.5))
            .velocityDecay(0.6)
            .alpha(0.5)
            .alphaDecay(0.02);

        // Create gradient for links
        const defs = svg.append('defs');
        const gradient = defs.append('linearGradient')
            .attr('id', 'linkGradient')
            .attr('gradientUnits', 'userSpaceOnUse');

        gradient.append('stop')
            .attr('offset', '0%')
            .attr('stop-color', COLORS.master);
        
        gradient.append('stop')
            .attr('offset', '100%')
            .attr('stop-color', COLORS.worker);

        // Update link styling
        const link = g.selectAll('.link')
            .data(data.links)
            .enter().append('g')
            .attr('class', 'link-group');

        // Add glowing link path
        link.append('path')
            .attr('class', 'link-glow')
            .style('stroke', 'url(#linkGradient)')
            .style('stroke-width', 4)
            .style('stroke-opacity', 0.2)
            .style('fill', 'none');

        // Add main link path
        link.append('path')
            .attr('class', 'link-main')
            .style('stroke', 'url(#linkGradient)')
            .style('stroke-width', 2)
            .style('stroke-opacity', 0.8)
            .style('fill', 'none')
            .style('stroke-dasharray', '10,5');

        // Add directional arrows
        const marker = defs.append('marker')
            .attr('id', 'arrowhead')
            .attr('viewBox', '-10 -5 10 10')
            .attr('refX', 0)
            .attr('refY', 0)
            .attr('markerWidth', 6)
            .attr('markerHeight', 6)
            .attr('orient', 'auto');

        marker.append('path')
            .attr('d', 'M -10,-5 L 0,0 L -10,5')
            .style('fill', COLORS.text);

        // Update the tick function
        simulation.on('tick', () => {
            link.selectAll('path')
                .attr('d', d => {
                    const dx = d.target.x - d.source.x;
                    const dy = d.target.y - d.source.y;
                    const dr = Math.sqrt(dx * dx + dy * dy);
                    return `M${d.source.x},${d.source.y}A${dr},${dr} 0 0,1 ${d.target.x},${d.target.y}`;
                });

            node.attr('transform', d => `translate(${d.x},${d.y})`);
        });

        // Add glass-like effect to nodes
        const glassEffect = defs.append('filter')
            .attr('id', 'glass')
            .attr('x', '-50%')
            .attr('y', '-50%')
            .attr('width', '200%')
            .attr('height', '200%');

        glassEffect.append('feGaussianBlur')
            .attr('in', 'SourceAlpha')
            .attr('stdDeviation', '4')
            .attr('result', 'blur');

        glassEffect.append('feOffset')
            .attr('in', 'blur')
            .attr('dx', '2')
            .attr('dy', '2')
            .attr('result', 'offsetBlur');

        const feMerge = glassEffect.append('feMerge');
        feMerge.append('feMergeNode')
            .attr('in', 'offsetBlur');
        feMerge.append('feMergeNode')
            .attr('in', 'SourceGraphic');

        // Update node styling with glass effect
        node.selectAll('rect')
            .style('filter', 'url(#glass)');

        // Update node styling
        const node = g.selectAll('.node')
            .data(data.nodes)
            .enter().append('g')
            .attr('class', d => 'node ' + d.role)
            .call(drag(simulation));

        // Calculate node dimensions
        node.each(function(d) {
            const gpuCount = d.info.gpu_info?.length || 0;
            d.nodeWidth = 240;
            d.nodeHeight = 140 + (gpuCount * 20);
        });

        // Add glowing rectangle behind main rectangle
        node.append('rect')
            .attr('class', 'glow')
            .attr('width', d => d.nodeWidth + 4)
            .attr('height', d => d.nodeHeight + 4)
            .attr('x', d => -d.nodeWidth / 2 - 2)
            .attr('y', d => -d.nodeHeight / 2 - 2)
            .attr('rx', 12)
            .attr('ry', 12)
            .style('fill', 'none')
            .style('stroke', d => d.role === 'master' ? COLORS.master : COLORS.worker)
            .style('stroke-width', 2)
            .style('filter', 'url(#glow)');

        // Add main rectangle
        node.append('rect')
            .attr('width', d => d.nodeWidth)
            .attr('height', d => d.nodeHeight)
            .attr('x', d => -d.nodeWidth / 2)
            .attr('y', d => -d.nodeHeight / 2)
            .attr('rx', 10)
            .attr('ry', 10)
            .style('fill', COLORS.background)
            .style('stroke', d => d.role === 'master' ? COLORS.master : COLORS.worker)
            .style('stroke-width', 2);

        // Add GPU information display
        node.each(function(d) {
            const gpus = d.info.gpu_info || [];
            if (gpus.length > 0) {
                const gpuGroup = d3.select(this);
                gpus.forEach((gpu, i) => {
                    gpuGroup.append('text')
                        .attr('text-anchor', 'middle')
                        .attr('dy', -d.nodeHeight / 2 + 100 + i * 20)
                        .text(`GPU ${i + 1}: ${gpu.name} (${formatBytes(gpu.current_memory)}/${formatBytes(gpu.total_memory)})`)
                        .style('fill', COLORS.text)
                        .style('font-size', '12px');
                });
            }
        });

        // Add glow filter here instead of creating new defs
        const filter = defs.append('filter')
            .attr('id', 'glow');

        filter.append('feGaussianBlur')
            .attr('stdDeviation', '2')
            .attr('result', 'coloredBlur');

        filter.append('feMerge')
            .append('feMergeNode')
            .attr('in', 'coloredBlur');

        // Add pulsing animation
        node.selectAll('.glow')
            .style('animation', 'pulse 2s infinite');

        // Append text elements
        node.append('text')
            .attr('text-anchor', 'middle')
            .attr('dy', d => -d.nodeHeight / 2 + 20)
            .text(d => d.id)
            .style('fill', COLORS.text)
            .style('font-size', '14px')
            .style('font-weight', 'bold');

        node.append('text')
            .attr('text-anchor', 'middle')
            .attr('dy', d => -d.nodeHeight / 2 + 40)
            .text(d => `${d.info.hostname} (${d.role})`)
            .style('fill', COLORS.text)
            .style('font-size', '12px');

        node.append('text')
            .attr('text-anchor', 'middle')
            .attr('dy', d => -d.nodeHeight / 2 + 60)
            .text(d => `CPU: ${d.info.cpu_count} cores @ ${(d.info.cpu_freq / 1000).toFixed(2)} GHz`)
            .style('fill', COLORS.text)
            .style('font-size', '12px');

        node.append('text')
            .attr('text-anchor', 'middle')
            .attr('dy', d => -d.nodeHeight / 2 + 80)
            .text(d => `RAM: ${formatBytes(d.info.available_memory)} / ${formatBytes(d.info.total_memory)}`)
            .style('fill', COLORS.text)
            .style('font-size', '12px');

        // Add tooltips
        node.on('mouseover', (event, d) => {
            showTooltip(event, d);
        }).on('mouseout', hideTooltip);
    }

    function drag(simulation) {
        function dragstarted(event, d) {
            if (!event.active) simulation.alphaTarget(0.3).restart();
            d.fx = d.x;
            d.fy = d.y;
        }
        
        function dragged(event, d) {
            d.fx = event.x;
            d.fy = event.y;
        }
        
        function dragended(event, d) {
            if (!event.active) simulation.alphaTarget(0);
            d.fx = null;
            d.fy = null;
        }
        
        return d3.drag()
            .on('start', dragstarted)
            .on('drag', dragged)
            .on('end', dragended);
    }

    function showTooltip(event, d) {
        const tooltip = d3.select('.tooltip');
        let tooltipContent = `<strong>${d.id}</strong><br>
                              Hostname: ${d.info.hostname}<br>
                              Role: ${d.role}<br>
                              CPU: ${d.info.cpu_count} cores @ ${(d.info.cpu_freq / 1000).toFixed(2)} GHz<br>
                              RAM: ${formatBytes(d.info.available_memory)} / ${formatBytes(d.info.total_memory)}<br>`;
        if (d.info.gpu_count > 0) {
            tooltipContent += `<br><strong>GPU Information:</strong><br>`;
            d.info.gpu_info.forEach((gpu, i) => {
                tooltipContent += `GPU ${i + 1}: ${gpu.name}<br>
                                   Memory: ${formatBytes(gpu.current_memory)} / ${formatBytes(gpu.total_memory)}<br>`;
            });
        }

        tooltip.style('display', 'block')
            .style('left', (event.pageX + 15) + 'px')
            .style('top', (event.pageY + 15) + 'px')
            .html(tooltipContent);
    }

    function hideTooltip() {
        d3.select('.tooltip').style('display', 'none');
    }

    // Initialize WebSocket connection
    connectWebSocket();

    // Helper function to format bytes
    function formatBytes(bytes) {
        const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
        if (bytes === 0) return '0 B';
        const i = Math.floor(Math.log(bytes) / Math.log(1024));
        return parseFloat((bytes / Math.pow(1024, i)).toFixed(2)) + ' ' + sizes[i];
    }
})();