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

    function updateVisualization(data) {
        if (!data || !data.nodes || !data.links) {
            console.warn('Invalid topology data received');
            return;
        }

        // Clear previous visualization
        g.selectAll('*').remove();

        // Create simulation
        const simulation = d3.forceSimulation(data.nodes)
            .force('link', d3.forceLink(data.links).id(d => d.id).distance(200))
            .force('charge', d3.forceManyBody().strength(-500))
            .force('center', d3.forceCenter(width / 2, height / 2));

        // Create links
        const link = g.selectAll('.link')
            .data(data.links)
            .enter().append('line')
            .attr('class', 'link')
            .style('stroke', '#999')
            .style('stroke-opacity', 0.6)
            .style('stroke-width', 2);

        // Create nodes
        const node = g.selectAll('.node')
            .data(data.nodes)
            .enter().append('g')
            .attr('class', d => 'node ' + d.role)
            .call(drag(simulation));

        // Append rectangles
        node.append('rect')
            .attr('width', 200)
            .attr('height', 100)
            .attr('x', -100)
            .attr('y', -50)
            .attr('rx', 10)
            .attr('ry', 10)
            .style('fill', '#1a1a1a')
            .style('stroke', '#33ff33')
            .style('stroke-width', 2);

        // Append text
        node.append('text')
            .attr('text-anchor', 'middle')
            .attr('dy', '-20')
            .text(d => d.id)
            .style('fill', '#33ff33')
            .style('font-size', '14px');

        node.append('text')
            .attr('text-anchor', 'middle')
            .attr('dy', '0')
            .text(d => `${d.info.hostname} (${d.role})`)
            .style('fill', '#33ff33')
            .style('font-size', '12px');

        node.append('text')
            .attr('text-anchor', 'middle')
            .attr('dy', '20')
            .text(d => `CPU: ${d.info.cpu_count} cores`)
            .style('fill', '#33ff33')
            .style('font-size', '12px');

        node.append('text')
            .attr('text-anchor', 'middle')
            .attr('dy', '40')
            .text(d => `RAM: ${formatBytes(d.info.available_memory)} / ${formatBytes(d.info.total_memory)}`)
            .style('fill', '#33ff33')
            .style('font-size', '12px');

        // Update positions
        simulation.on('tick', () => {
            link
                .attr('x1', d => d.source.x)
                .attr('y1', d => d.source.y)
                .attr('x2', d => d.target.x)
                .attr('y2', d => d.target.y);

            node
                .attr('transform', d => `translate(${d.x}, ${d.y})`);
        });

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
        tooltip.style('display', 'block')
            .style('left', (event.pageX + 10) + 'px')
            .style('top', (event.pageY + 10) + 'px')
            .html(`<strong>${d.id}</strong><br>
                   Hostname: ${d.info.hostname}<br>
                   Role: ${d.role}<br>
                   CPU: ${d.info.cpu_count} cores<br>
                   RAM: ${formatBytes(d.info.available_memory)} / ${formatBytes(d.info.total_memory)}<br>`);
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