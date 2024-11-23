// topology.js
(function() {
    // Initialize D3 visualization
    const width = window.innerWidth;
    const height = window.innerHeight;

    const COLORS = {
        master: {
            border: '#00ff44',
            glow: 'rgba(0, 255, 68, 0.5)',
            text: '#00ff44',
            gradient: {
                start: '#00ff44',
                end: '#00cc44'
            }
        },
        worker: {
            border: '#00ccff',
            glow: 'rgba(0, 204, 255, 0.5)',
            text: '#00ccff',
            gradient: {
                start: '#00ccff',
                end: '#0099ff'
            }
        },
        gpu: {
            active: '#ff3366',
            idle: '#2a4858',
            memory: '#00ff44',
            text: '#e0ffe0',
            usage: {
                high: '#ff3366',
                medium: '#ffaa00',
                low: '#00ff44'
            },
            bar: {
                background: 'rgba(0, 20, 0, 0.3)',
                border: 'rgba(0, 255, 68, 0.2)',
                gradient: {
                    low: '#00ff44',
                    mid: '#ffaa00',
                    high: '#ff3366'
                }
            }
        },
        text: {
            primary: '#e0ffe0',
            secondary: 'rgba(224, 255, 224, 0.8)',
            stats: '#00ff44'
        },
        background: {
            node: 'rgba(0, 20, 0, 0.85)',
            terminal: '#000000'
        },
        link: {
            active: 'rgba(0, 255, 68, 0.6)',
            inactive: 'rgba(0, 255, 68, 0.2)',
            gradient: {
                start: 'rgba(0, 255, 68, 0.8)',
                end: 'rgba(0, 204, 255, 0.8)'
            },
            glow: 'rgba(0, 255, 68, 0.2)',
            dash: {
                primary: 'rgba(0, 255, 68, 0.8)',
                secondary: 'rgba(0, 204, 255, 0.8)',
                glow: 'rgba(0, 255, 68, 0.2)'
            },
            flow: {
                active: '#00ff44',
                inactive: '#2a4858'
            }
        },
        memory: {
            used: '#ff3366',
            available: '#00ff44',
            background: 'rgba(0, 255, 68, 0.1)'
        }
    };

    const LAYOUT = {
        nodeSpacing: 400,
        masterNodeSize: { width: 320, height: 200 },
        workerNodeSize: { width: 280, height: 160 }
    };

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

    // Create defs for gradients and filters once
    const defs = svg.append('defs');
    setupGradients(defs);
    setupFilters(defs);

    function updateVisualization(data) {
        if (!data || !data.nodes || !data.links) return;

        // Clear previous visualization
        g.selectAll('*').remove();

        // Set fixed positions for nodes first
        const masterNode = data.nodes.find(n => n.role === 'master');
        const workers = data.nodes.filter(n => n.role === 'worker');
        
        // Position master in center
        if (masterNode) {
            masterNode.x = width / 2;
            masterNode.y = height / 2;
        }

        // Position workers to the right of master
        workers.forEach((node, i) => {
            node.x = (width / 2) + LAYOUT.nodeSpacing;
            node.y = height / 2;
        });

        // Create links with proper source/target references
        const links = data.links.map(link => ({
            source: data.nodes.find(n => n.id === link.source) || link.source,
            target: data.nodes.find(n => n.id === link.target) || link.target
        }));

        // Create connections
        links.forEach(link => {
            if (!link.source.x || !link.target.x) return; // Skip if positions aren't set

            // Create connection group
            const connectionGroup = g.append('g')
                .attr('class', 'connection-group');

            // Glowing background line
            connectionGroup.append('path')
                .attr('class', 'connection-glow')
                .attr('d', `M${link.source.x},${link.source.y} L${link.target.x},${link.target.y}`)
                .style('stroke', COLORS.link.glow)
                .style('stroke-width', '6')
                .style('stroke-dasharray', '10,5')
                .style('opacity', 0.3)
                .style('fill', 'none');

            // Main connection line
            connectionGroup.append('path')
                .attr('class', 'connection-line')
                .attr('d', `M${link.source.x},${link.source.y} L${link.target.x},${link.target.y}`)
                .style('stroke', COLORS.link.dash.primary)
                .style('stroke-width', '2')
                .style('stroke-dasharray', '10,5')
                .style('opacity', 0.8)
                .style('fill', 'none');

            // Add data flow particles
            const particleGroup = connectionGroup.append('g')
                .attr('class', 'particle-group');

            // Calculate the angle for proper particle movement
            const dx = link.target.x - link.source.x;
            const dy = link.target.y - link.source.y;
            const angle = Math.atan2(dy, dx) * 180 / Math.PI;

            [0, 0.33, 0.66].forEach(offset => {
                particleGroup.append('circle')
                    .attr('class', 'flow-particle')
                    .attr('r', 2)
                    .attr('transform', `translate(${link.source.x},${link.source.y})`)
                    .style('fill', COLORS.link.flow.active)
                    .style('filter', 'url(#glow)')
                    .style('animation', `particleFlow 2s infinite linear ${offset}s`)
                    .style('transform-origin', `${link.source.x}px ${link.source.y}px`);
            });
        });

        // Create nodes
        const node = g.selectAll('.node')
            .data(data.nodes)
            .enter()
            .append('g')
            .attr('class', d => `node ${d.role}`)
            .attr('transform', d => `translate(${d.x},${d.y})`);

        // Add node visuals
        node.each(function(d) {
            const el = d3.select(this);
            const size = d.role === 'master' ? LAYOUT.masterNodeSize : LAYOUT.workerNodeSize;
            const colors = d.role === 'master' ? COLORS.master : COLORS.worker;

            // Glowing background
            el.append('rect')
                .attr('class', 'node-glow')
                .attr('width', size.width + 4)
                .attr('height', size.height + 4)
                .attr('x', -(size.width + 4) / 2)
                .attr('y', -(size.height + 4) / 2)
                .attr('rx', 12)
                .style('fill', 'none')
                .style('stroke', colors.glow)
                .style('stroke-width', 2)
                .style('filter', 'url(#glow)');

            // Main rectangle
            el.append('rect')
                .attr('class', 'node-main')
                .attr('width', size.width)
                .attr('height', size.height)
                .attr('x', -size.width / 2)
                .attr('y', -size.height / 2)
                .attr('rx', 10)
                .style('fill', COLORS.background.node)
                .style('stroke', colors.border)
                .style('stroke-width', 2);

            // Node content group
            const content = el.append('g')
                .attr('class', 'node-content');

            // Hostname
            content.append('text')
                .attr('class', 'hostname')
                .attr('text-anchor', 'middle')
                .attr('y', -size.height/2 + 30)
                .style('fill', colors.text)
                .style('font-size', '16px')
                .style('font-weight', 'bold')
                .text(d.id.split('-')[0]);

            content.append('text')
                .attr('class', 'role')
                .attr('text-anchor', 'middle')
                .attr('y', -size.height/2 + 50)
                .style('fill', COLORS.text.secondary)
                .style('font-size', '12px')
                .text(`(${d.role})`);

            // CPU info
            content.append('text')
                .attr('class', 'cpu-info')
                .attr('text-anchor', 'middle')
                .attr('y', -size.height/2 + 80)
                .style('fill', COLORS.text.primary)
                .style('font-size', '12px')
                .text(`CPU: ${d.info.cpu_count} cores @ ${(d.info.cpu_freq/1000).toFixed(2)} GHz`);

            // GPU information
            if (d.info.gpu_info) {
                d.info.gpu_info.forEach((gpu, i) => {
                    const gpuY = -size.height/2 + 110 + (i * 50);
                    
                    // GPU name
                    content.append('text')
                        .attr('class', 'gpu-name')
                        .attr('text-anchor', 'middle')
                        .attr('y', gpuY)
                        .style('fill', COLORS.text.primary)
                        .style('font-size', '12px')
                        .text(`GPU ${i + 1}: ${gpu.name.split('NVIDIA ')[1]}`);

                    // GPU utilization bar
                    const barWidth = size.width - 60;
                    const barGroup = content.append('g')
                        .attr('transform', `translate(${-barWidth/2}, ${gpuY + 10})`);

                    // Background bar
                    barGroup.append('rect')
                        .attr('width', barWidth)
                        .attr('height', 6)
                        .attr('rx', 3)
                        .style('fill', COLORS.gpu.idle);

                    // Utilization bar
                    const utilization = Number(gpu.gpu_util || 0);
                    barGroup.append('rect')
                        .attr('class', 'gpu-util-bar')
                        .attr('width', barWidth * (utilization / 100))
                        .attr('height', 6)
                        .attr('rx', 3)
                        .style('fill', utilization > 70 ? COLORS.gpu.usage.high :
                                      utilization > 30 ? COLORS.gpu.usage.medium :
                                      COLORS.gpu.usage.low)
                        .style('filter', 'url(#glow)');

                    // Utilization percentage
                    barGroup.append('text')
                        .attr('x', barWidth + 10)
                        .attr('y', 6)
                        .style('fill', COLORS.text.stats)
                        .style('font-size', '11px')
                        .text(`${utilization}%`);

                    // Memory info
                    const memoryText = content.append('text')
                        .attr('class', 'gpu-memory')
                        .attr('text-anchor', 'middle')
                        .attr('y', gpuY + 30)
                        .style('fill', COLORS.text.secondary)
                        .style('font-size', '11px')
                        .text(`Memory: ${formatBytes(gpu.current_memory)} / ${formatBytes(gpu.total_memory)}`);
                });
            }
        });

        // Add hover effects
        node.on('mouseover', function() {
            d3.select(this).select('.node-glow')
                .style('stroke-width', '4')
                .style('filter', 'url(#glow) brightness(1.2)');
        })
        .on('mouseout', function() {
            d3.select(this).select('.node-glow')
                .style('stroke-width', '2')
                .style('filter', 'url(#glow)');
        });

        // Update styles
        const newStyles = `
            @keyframes particleFlow {
                0% {
                    transform: translate(0, 0);
                    opacity: 0;
                }
                10% {
                    opacity: 1;
                }
                90% {
                    opacity: 1;
                }
                100% {
                    transform: translate(400px, 0);
                    opacity: 0;
                }
            }

            .connection-line {
                animation: dashOffset 20s linear infinite;
            }

            @keyframes dashOffset {
                from {
                    stroke-dashoffset: 0;
                }
                to {
                    stroke-dashoffset: -100;
                }
            }

            .connection-group {
                pointer-events: none;
            }
        `;

        // Add or update styles
        let styleSheet = document.getElementById('topology-styles');
        if (!styleSheet) {
            styleSheet = document.createElement('style');
            styleSheet.id = 'topology-styles';
            document.head.appendChild(styleSheet);
        }
        styleSheet.textContent += newStyles;
    }

    // WebSocket setup
    setupWebSocket();

    function setupWebSocket() {
        const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${wsProtocol}//${window.location.hostname}:${window.location.port}/ws`;
        
        const ws = new WebSocket(wsUrl);
        
        ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                if (data.nodes) {
                    data.nodes.forEach(node => {
                        if (node.info.gpu_info) {
                            node.info.gpu_info = node.info.gpu_info.map(gpu => ({
                                name: gpu.name || 'Unknown GPU',
                                memory_total: Number(gpu.total_memory || 0),
                                memory_used: Number(gpu.current_memory || 0),
                                gpu_util: Number(gpu.utilization || 0),
                                temperature: Number(gpu.temperature || 0),
                                power_draw: Number(gpu.power_draw || 0)
                            }));
                        }
                    });
                    updateVisualization(data);
                }
            } catch (e) {
                console.error('Error processing message:', e);
            }
        };

        ws.onclose = () => setTimeout(setupWebSocket, 2000);
    }

    // Helper functions
    function formatBytes(bytes) {
        const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
        if (bytes === 0) return '0 B';
        const i = Math.floor(Math.log(bytes) / Math.log(1024));
        return parseFloat((bytes / Math.pow(1024, i)).toFixed(2)) + ' ' + sizes[i];
    }

    function addNodeText(el, d, size) {
        addNodeVisuals(el, d);
    }

    // Add these functions after the defs creation
    function setupGradients(defs) {
        const linkGradient = defs.append('linearGradient')
            .attr('id', 'linkGradient')
            .attr('gradientUnits', 'userSpaceOnUse');

        linkGradient.append('stop')
            .attr('offset', '0%')
            .attr('stop-color', COLORS.master.border)
            .attr('stop-opacity', 1);

        linkGradient.append('stop')
            .attr('offset', '100%')
            .attr('stop-color', COLORS.worker.border)
            .attr('stop-opacity', 1);

        // Add more gradients if needed...
    }

    function setupFilters(defs) {
        const glow = defs.append('filter')
            .attr('id', 'glow')
            .attr('height', '300%')
            .attr('width', '300%')
            .attr('x', '-100%')
            .attr('y', '-100%');

        glow.append('feGaussianBlur')
            .attr('stdDeviation', '3')
            .attr('result', 'coloredBlur');

        const feMerge = glow.append('feMerge');
        feMerge.append('feMergeNode')
            .attr('in', 'coloredBlur');
        feMerge.append('feMergeNode')
            .attr('in', 'SourceGraphic');

        // Add glass effect
        const glassFilter = defs.append('filter')
            .attr('id', 'glass')
            .attr('x', '-50%')
            .attr('y', '-50%')
            .attr('width', '200%')
            .attr('height', '200%');

        glassFilter.append('feGaussianBlur')
            .attr('in', 'SourceAlpha')
            .attr('stdDeviation', '4')
            .attr('result', 'blur');

        glassFilter.append('feOffset')
            .attr('in', 'blur')
            .attr('dx', '2')
            .attr('dy', '2')
            .attr('result', 'offsetBlur');

        const feMergeGlass = glassFilter.append('feMerge');
        feMergeGlass.append('feMergeNode')
            .attr('in', 'offsetBlur');
        feMergeGlass.append('feMergeNode')
            .attr('in', 'SourceGraphic');
    }

    // Update the initial node positioning
    function initialNodePositions(nodes) {
        const masterNode = nodes.find(n => n.role === 'master');
        if (masterNode) {
            masterNode.x = width / 2;
            masterNode.y = height / 2;
            masterNode.fx = width / 2;  // Fix position
            masterNode.fy = height / 2;
        }

        const workers = nodes.filter(n => n.role === 'worker');
        const radius = LAYOUT.nodeSpacing;
        workers.forEach((node, i) => {
            const angle = (2 * Math.PI * i) / Math.max(1, workers.length);
            node.x = width/2 + radius * Math.cos(angle);
            node.y = height/2 + radius * Math.sin(angle);
        });
    }

    // Add memory bar visualization
    function addMemoryBar(el, d, size) {
        const barHeight = 6;
        const barWidth = size.width - 40;
        const memoryUsed = d.info.total_memory - d.info.available_memory;
        const memoryPercent = (memoryUsed / d.info.total_memory) * 100;

        const barGroup = el.append('g')
            .attr('class', 'memory-stats')
            .attr('transform', `translate(${-barWidth/2}, ${size.height/2 - 30})`);

        // Background bar
        barGroup.append('rect')
            .attr('width', barWidth)
            .attr('height', barHeight)
            .attr('rx', 3)
            .style('fill', COLORS.memory.background);

        // Used memory bar
        barGroup.append('rect')
            .attr('width', barWidth * (memoryUsed / d.info.total_memory))
            .attr('height', barHeight)
            .attr('rx', 3)
            .style('fill', COLORS.memory.used)
            .style('filter', 'url(#glow)');

        // Memory percentage text
        barGroup.append('text')
            .attr('x', barWidth + 10)
            .attr('y', barHeight)
            .style('fill', COLORS.text.stats)
            .style('font-size', '11px')
            .text(`${memoryPercent.toFixed(1)}%`);
    }

    // Enhanced GPU bar with modern styling
    function addGPUBar(parent, gpu, width, y) {
        const barHeight = 8;
        const barGroup = parent.append('g')
            .attr('class', 'gpu-bar-group')
            .attr('transform', `translate(${-width/2}, ${y})`);

        // Background with subtle pattern
        const pattern = defs.append('pattern')
            .attr('id', `gpu-pattern-${Math.random().toString(36)}`)
            .attr('patternUnits', 'userSpaceOnUse')
            .attr('width', 10)
            .attr('height', 10)
            .attr('patternTransform', 'rotate(45)');

        pattern.append('line')
            .attr('x1', 0)
            .attr('y1', 0)
            .attr('x2', 0)
            .attr('y2', 10)
            .style('stroke', COLORS.gpu.bar.border)
            .style('stroke-width', 1);

        // Enhanced background
        barGroup.append('rect')
            .attr('width', width)
            .attr('height', barHeight)
            .attr('rx', 4)
            .style('fill', `url(#${pattern.attr('id')})`)
            .style('stroke', COLORS.gpu.bar.border)
            .style('stroke-width', 1);

        // Utilization gradient
        const gradientId = `gpu-gradient-${Math.random().toString(36)}`;
        const gradient = defs.append('linearGradient')
            .attr('id', gradientId)
            .attr('x1', '0%')
            .attr('x2', '100%');

        gradient.append('stop')
            .attr('offset', '0%')
            .attr('stop-color', COLORS.gpu.bar.gradient.low);
        gradient.append('stop')
            .attr('offset', '50%')
            .attr('stop-color', COLORS.gpu.bar.gradient.mid);
        gradient.append('stop')
            .attr('offset', '100%')
            .attr('stop-color', COLORS.gpu.bar.gradient.high);

        // Utilization bar
        const utilization = Number(gpu.gpu_util || 0);
        const utilizationBar = barGroup.append('rect')
            .attr('class', 'gpu-bar')
            .attr('width', (width * utilization / 100) || 0)
            .attr('height', barHeight)
            .attr('rx', 4)
            .style('fill', `url(#${gradientId})`)
            .style('filter', 'url(#glow)');

        // Stats container
        const stats = barGroup.append('g')
            .attr('class', 'gpu-stats')
            .attr('transform', `translate(${width + 10}, ${barHeight/2})`);

        // Utilization percentage
        stats.append('text')
            .attr('class', 'stats-value')
            .attr('dy', '0.32em')
            .text(`${Math.round(utilization)}%`);

        // Memory usage
        if (gpu.memory_used && gpu.memory_total) {
            const memoryPercent = (gpu.memory_used / gpu.memory_total * 100).toFixed(1);
            stats.append('text')
                .attr('class', 'gpu-stat')
                .attr('x', 45)
                .attr('dy', '0.32em')
                .text(`Mem: ${memoryPercent}%`);
        }

        return barGroup;
    }

    // Update node visuals
    function addNodeVisuals(el, d) {
        const size = d.role === 'master' ? LAYOUT.masterNodeSize : LAYOUT.workerNodeSize;
        const colors = d.role === 'master' ? COLORS.master : COLORS.worker;

        // Create a container for the background elements
        const background = el.append('g')
            .attr('class', 'node-background');

        // Glowing background
        background.append('rect')
            .attr('class', 'node-glow')
            .attr('width', size.width + 4)
            .attr('height', size.height + 4)
            .attr('x', -(size.width + 4) / 2)
            .attr('y', -(size.height + 4) / 2)
            .attr('rx', 12)
            .style('fill', 'none')
            .style('stroke', colors.glow)
            .style('stroke-width', 2)
            .style('filter', 'url(#glow)');

        // Main rectangle
        background.append('rect')
            .attr('class', 'node-main')
            .attr('width', size.width)
            .attr('height', size.height)
            .attr('x', -size.width / 2)
            .attr('y', -size.height / 2)
            .attr('rx', 10)
            .style('fill', COLORS.background.node)
            .style('stroke', colors.border)
            .style('stroke-width', 2);

        // Add hostname and role
        el.append('text')
            .attr('class', 'hostname')
            .attr('text-anchor', 'middle')
            .attr('y', -size.height/2 + 30)
            .style('fill', colors.text)
            .style('font-size', '16px')
            .style('font-weight', 'bold')
            .text(d.info.hostname);

        el.append('text')
            .attr('class', 'role')
            .attr('text-anchor', 'middle')
            .attr('y', -size.height/2 + 50)
            .style('fill', COLORS.text.secondary)
            .style('font-size', '12px')
            .text(`(${d.role})`);

        // Add system stats
        const statsGroup = el.append('g')
            .attr('class', 'stats')
            .attr('transform', `translate(0, ${-size.height/2 + 80})`);

        // CPU info
        statsGroup.append('text')
            .attr('text-anchor', 'middle')
            .style('fill', COLORS.text.primary)
            .style('font-size', '12px')
            .text(`CPU: ${d.info.cpu_count} cores @ ${(d.info.cpu_freq/1000).toFixed(2)} GHz`);

        // Add memory bar
        addMemoryBar(el, d, size);

        // Add GPU information
        if (d.info.gpu_info) {
            d.info.gpu_info.forEach((gpu, i) => {
                addGPUBars(el, d, size, gpu, i);
            });
        }
    }

    // Update the styles section with better hover handling
    const styles = `
        @keyframes pulse {
            0% { opacity: 0.8; }
            50% { opacity: 1; }
            100% { opacity: 0.8; }
        }

        @keyframes connectionFlow {
            0% { stroke-dashoffset: 24; }
            100% { stroke-dashoffset: 0; }
        }

        .connection-line {
            animation: connectionFlow 1s linear infinite;
        }

        .connection-glow {
            animation: connectionFlow 1s linear infinite;
        }

        .node {
            transition: filter 0.3s ease;
        }

        .node:hover .node-glow {
            stroke-width: 3;
            filter: url(#glow);
        }

        .node:hover .node-main {
            filter: brightness(1.1);
        }

        .node-glow {
            transition: stroke-width 0.3s ease, filter 0.3s ease;
        }

        .node-main {
            transition: filter 0.3s ease;
        }

        .gpu-stats rect {
            transition: all 0.3s ease;
        }

        .text-content {
            pointer-events: none;
            user-select: none;
        }

        .link-group {
            pointer-events: none;
        }

        @keyframes flowParticle {
            0% {
                offset-distance: 0%;
                opacity: 0;
            }
            10% {
                opacity: 1;
            }
            90% {
                opacity: 1;
            }
            100% {
                offset-distance: 100%;
                opacity: 0;
            }
        }

        .flow-particle {
            offset-path: path('M0,0 L100,0');
            animation: flowParticle 2s infinite linear;
        }

        .node {
            backdrop-filter: blur(5px);
            -webkit-backdrop-filter: blur(5px);
        }

        .node-glow {
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        }

        .node:hover .node-glow {
            stroke-width: 4;
            filter: url(#glow) brightness(1.2);
        }

        .gpu-bar {
            transition: width 0.3s ease-out;
        }

        .connection-line {
            stroke-linecap: round;
            animation: dashFlow 30s linear infinite;
        }

        @keyframes dashFlow {
            to {
                stroke-dashoffset: -1000;
            }
        }

        .stats-value {
            font-family: 'Courier New', monospace;
            font-weight: bold;
        }

        .gpu-label {
            font-size: 12px;
            fill: ${COLORS.text.primary};
            font-weight: 500;
        }

        .gpu-stat {
            font-size: 11px;
            fill: ${COLORS.text.secondary};
        }

        .node-container {
            transform-origin: center;
            transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        }

        .node-container:hover {
            transform: scale(1.02);
        }
    `;

    // Add the styles to document
    const styleSheet = document.createElement('style');
    styleSheet.textContent = styles;
    document.head.appendChild(styleSheet);
})();