// topology.js
(function() {
    // WebSocket connection
    let ws = null;
    let isConnecting = false;  // Add connection flag
    let reconnectTimer = null;

    // Declare updateNodeGraph at the module scope
    let updateNodeGraph;

    // Clear any existing connections on page load/reload
    window.addEventListener('beforeunload', () => {
        if (ws) {
            ws.close();
            ws = null;
        }
    });
    
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
            gpuWorker: {  // Added for GPU workers
                border: '#ff3366',
                glow: 'rgba(255, 51, 102, 0.5)',
                text: '#ff3366',
                gradient: {
                    start: '#ff3366',
                    end: '#cc2952'
                }
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
        workerNodeSize: { width: 280, height: 160 },
        gpuWorkerNodeSize: { width: 280, height: 220 }  // Added for GPU workers
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
        if (!data.nodes || !Array.isArray(data.nodes)) {
            console.error('Invalid node data format:', data);
            return;
        }

        // Aggregate stats across all nodes
        const stats = data.nodes.reduce((acc, node) => {
            if (node.info) {
                // CPU Usage
                acc.cpuUsage += node.info.cpu_percent || 0;
                
                // Memory
                acc.totalMemory += node.info.total_memory || 0;
                acc.usedMemory += (node.info.total_memory - node.info.available_memory) || 0;
                
                // GPU Memory
                if (node.info.gpu_info) {
                    node.info.gpu_info.forEach(gpu => {
                        acc.totalGPUMemory += gpu.total_memory || 0;
                        acc.usedGPUMemory += gpu.current_memory || 0;
                    });
                }
            }
            return acc;
        }, {
            cpuUsage: 0,
            totalMemory: 0,
            usedMemory: 0,
            totalGPUMemory: 0,
            usedGPUMemory: 0
        });

        // Update UI elements
        document.querySelector('.cpu-usage').textContent = 
            `${Math.round(stats.cpuUsage / data.nodes.length)}%`;
        
        document.querySelector('.memory').textContent = 
            `Total: ${Math.round(stats.totalMemory)} GB`;
        document.querySelector('.memory-percent').textContent = 
            `${Math.round((stats.usedMemory / stats.totalMemory) * 100)}%`;
        
        document.querySelector('.gpu-memory').textContent = 
            `Total: ${Math.round(stats.totalGPUMemory)} GB`;
        document.querySelector('.gpu-percent').textContent = 
            `${Math.round((stats.usedGPUMemory / stats.totalGPUMemory) * 100)}%`;

        // Keep existing node visualization code
        updateNodeGraph(data);
    }

    // Helper functions
    function formatBytes(bytes) {
        const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
        if (bytes === 0) return '0 B';
        const i = Math.floor(Math.log(bytes) / Math.log(1024));
        return parseFloat((bytes / Math.pow(1024, i)).toFixed(2)) + ' ' + sizes[i];
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
        const barHeight = 6;
        const barGroup = parent.append('g')
            .attr('transform', `translate(${-width/2}, ${y})`);

        // Background bar
        barGroup.append('rect')
            .attr('width', width)
            .attr('height', barHeight)
            .attr('rx', 3)
            .style('fill', COLORS.gpu.idle);

        // Utilization bar
        const utilization = gpu.gpu_util || 0;
        barGroup.append('rect')
            .attr('width', width * (utilization/100))
            .attr('height', barHeight)
            .attr('rx', 3)
            .style('fill', utilization > 70 ? COLORS.gpu.usage.high :
                          utilization > 30 ? COLORS.gpu.usage.medium :
                          COLORS.gpu.usage.low);

        // Stats text
        barGroup.append('text')
            .attr('x', width + 5)
            .attr('y', barHeight)
            .style('fill', COLORS.gpu.text)
            .style('font-size', '11px')
            .text(`${utilization}%`);
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
            .text(`CPU: ${d.info.cpu_count} cores @ ${(d.info.cpu_freq / 1000).toFixed(2)} GHz`);

        // RAM info
        statsGroup.append('text')
            .attr('text-anchor', 'middle')
            .attr('dy', '20')
            .style('fill', COLORS.text.primary)
            .style('font-size', '12px')
            .text(`RAM: ${formatBytes(d.info.available_memory)} / ${formatBytes(d.info.total_memory)}`);

        // Add tooltips
        el.on('mouseover', (event, d) => {
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

    function initTopology() {
        // Initialize force simulation
        const simulation = d3.forceSimulation()
            .force('link', d3.forceLink().id(d => d.id).distance(200))
            .force('charge', d3.forceManyBody().strength(-1000))
            .force('center', d3.forceCenter(width / 2, height / 2))
            .force('collision', d3.forceCollide().radius(150));

        // Create the visualization containers
        const links = g.append('g').attr('class', 'links');
        const nodes = g.append('g').attr('class', 'nodes');

        // Assign updateNodeGraph to the module scope variable
        updateNodeGraph = function(data) {
            if (!data || !data.nodes) return;

            // Process the data
            const nodeData = data.nodes.map(node => ({
                id: node.id,
                role: node.role,
                info: node.info
            }));

            const linkData = data.links || [];

            // Update nodes
            const node = nodes.selectAll('.node')
                .data(nodeData, d => d.id);

            // Remove old nodes
            node.exit().remove();

            // Add new nodes
            const nodeEnter = node.enter()
                .append('g')
                .attr('class', 'node')
                .call(drag(simulation));

            // Add visuals to new nodes
            nodeEnter.each(function(d) {
                addNodeVisuals(d3.select(this), d);
            });

            // Update links
            const link = links.selectAll('.link')
                .data(linkData, d => `${d.source}-${d.target}`);

            // Remove old links
            link.exit().remove();

            // Add new links
            link.enter()
                .append('path')
                .attr('class', 'link')
                .style('stroke', 'url(#linkGradient)')
                .style('stroke-width', 2)
                .style('fill', 'none');

            // Update simulation
            simulation
                .nodes(nodeData)
                .force('link').links(linkData);

            simulation.alpha(1).restart();

            // Update positions on tick
            simulation.on('tick', () => {
                links.selectAll('.link').attr('d', d => {
                    const dx = d.target.x - d.source.x,
                          dy = d.target.y - d.source.y,
                          dr = Math.sqrt(dx * dx + dy * dy);
                    return `M${d.source.x},${d.source.y}A${dr},${dr} 0 0,1 ${d.target.x},${d.target.y}`;
                });

                nodes.selectAll('.node')
                    .attr('transform', d => `translate(${d.x},${d.y})`);
            });
        };
    }

    function connectWebSocket() {
        if (isConnecting || (ws && ws.readyState === WebSocket.OPEN)) return;
        
        isConnecting = true;
        clearTimeout(reconnectTimer);
        
        const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${wsProtocol}//${window.location.hostname}:${window.location.port}/ws`;
        
        if (ws) ws.close();
        
        ws = new WebSocket(wsUrl);
        ws.onopen = () => {
            isConnecting = false;
            document.querySelector('.connection-status').textContent = '● Connected';
        };

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
        
        ws.onclose = () => {
            isConnecting = false;
            document.querySelector('.connection-status').textContent = '● Disconnected';
            reconnectTimer = setTimeout(connectWebSocket, 5000);
        }
    }

    function init() {
        if (window.topologyInstance) {
            return;
        }
        window.topologyInstance = true;
        initTopology();
        connectWebSocket();
    }

    // Wait for DOM and ensure single initialization
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init, { once: true });
    } else {
        init();
    }
})();
