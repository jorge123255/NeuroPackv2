// Enhanced topology visualization
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

// Force simulation setup
const simulation = d3.forceSimulation()
    .force('link', d3.forceLink().id(d => d.id).distance(150))
    .force('charge', d3.forceManyBody().strength(-500))
    .force('center', d3.forceCenter(width / 2, height / 2))
    .force('collision', d3.forceCollide().radius(80));

// WebSocket connection
const ws = new WebSocket(`ws://${window.location.host}/ws`);

ws.onopen = () => {
    console.log('Connected to server');
    // Add visual indicator
    d3.select('#stats')
        .append('div')
        .attr('class', 'connection-status')
        .style('color', '#4CAF50')
        .text('● Connected to server');
};

ws.onclose = () => {
    console.log('Disconnected from server');
    // Update visual indicator
    d3.select('.connection-status')
        .style('color', '#ff4444')
        .text('● Disconnected from server');
};

ws.onerror = (error) => {
    console.error('WebSocket error:', error);
};

ws.onmessage = function(event) {
    console.log('Received data:', event.data);  // Debug log
    try {
        const data = JSON.parse(event.data);
        updateVisualization(data);
    } catch (e) {
        console.error('Error processing message:', e);
    }
};

let nodes = [];
let links = [];

// Tooltip setup
const tooltip = d3.select('.tooltip');

function formatBytes(bytes) {
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    if (bytes === 0) return '0 B';
    const i = parseInt(Math.floor(Math.log(bytes) / Math.log(1024)));
    return Math.round(bytes / Math.pow(1024, i), 2) + ' ' + sizes[i];
}

function updateStats(data) {
    const statsContent = d3.select('#stats-content');
    const totalNodes = data.nodes.length;
    const totalGPUs = data.nodes.reduce((acc, node) => acc + node.info.gpu_count, 0);
    const totalMemory = data.nodes.reduce((acc, node) => acc + node.info.total_memory, 0);

    statsContent.html(`
        +${'-'.repeat(30)}+
        |  Cluster Statistics        |
        +${'-'.repeat(30)}+
        |  Nodes: ${totalNodes.toString().padEnd(20)} |
        |  GPUs:  ${totalGPUs.toString().padEnd(20)} |
        |  Memory: ${formatBytes(totalMemory).padEnd(19)} |
        +${'-'.repeat(30)}+
    `.replace(/\n/g, '<br>'));
}

function showTooltip(d) {
    const info = d.info;
    const gpuInfo = info.gpu_info.map((gpu, i) => `
        GPU ${i + 1}: ${gpu.name}
        Memory: ${formatBytes(gpu.total_memory)}
        Compute: ${gpu.compute_capability.join('.')}
    `).join('\n');
    
    const memoryUsage = (info.total_memory - info.available_memory) / info.total_memory * 100;
    
    tooltip.style('display', 'block')
        .html(`
            <div style="font-size: 16px; font-weight: bold; margin-bottom: 10px;">
                ${d.id} (${d.role})
            </div>
            
            <div style="margin-bottom: 15px;">
                <div style="color: #4CAF50">● Online</div>
                <div>Platform: ${info.platform}</div>
                <div>${info.hostname} (${info.ip_address})</div>
            </div>
            
            <div style="margin-bottom: 15px;">
                <div style="font-weight: bold">Computing Resources:</div>
                <div>CPUs: ${info.cpu_count} cores @ ${(info.cpu_freq/1000).toFixed(2)} GHz</div>
                <div>Memory: ${formatBytes(info.available_memory)} / ${formatBytes(info.total_memory)} (${memoryUsage.toFixed(1)}% used)</div>
                <div>GPUs: ${info.gpu_count}</div>
                ${info.gpu_count > 0 ? `<pre style="margin: 5px 0">${gpuInfo}</pre>` : ''}
            </div>
            
            <div style="font-size: 12px; color: #888;">
                Click to view detailed metrics
            </div>
        `);
}

function hideTooltip() {
    tooltip.style('display', 'none');
}

// Add ASCII art styling
const style = document.createElement('style');
style.textContent = `
    .node text {
        font-family: 'Courier New', monospace;
        fill: #33ff33;
        font-size: 14px;
    }
    .link {
        stroke: #33ff33;
        stroke-width: 2px;
        stroke-dasharray: 5,5;
    }
    .node-box {
        fill: none;
        stroke: #33ff33;
        stroke-width: 2px;
    }
    .stats-box {
        fill: rgba(0, 0, 0, 0.5);
        stroke: #33ff33;
        stroke-width: 2px;
    }
    .ascii-decoration {
        fill: none;
        stroke: #33ff33;
        stroke-width: 1px;
    }
    .gpu-meter {
        fill: #1a1a1a;
        stroke: #33ff33;
    }
    .gpu-meter-fill {
        fill: #33ff33;
    }
    .cluster-title {
        font-family: 'Courier New', monospace;
        fill: #33ff33;
        font-size: 24px;
    }
`;
document.head.appendChild(style);

// Add cluster title with ASCII art border
function addClusterTitle(svg) {
    const title = svg.append('g')
        .attr('class', 'cluster-header')
        .attr('transform', `translate(${width/2}, 40)`);

    title.append('text')
        .attr('class', 'cluster-title')
        .attr('text-anchor', 'middle')
        .text('NeuroPack Cluster');

    // ASCII border around title
    title.append('path')
        .attr('class', 'ascii-decoration')
        .attr('d', `M-150,-20 L-140,-20 M140,-20 L150,-20 M-150,20 L-140,20 M140,20 L150,20
                   M-150,-20 L-150,20 M150,-20 L150,20`);
}

function createNodeBox(node) {
    const nodeGroup = d3.select(this);
    const info = node.info;
    
    // Create ASCII-style box
    const boxWidth = 280;
    const boxHeight = info.gpu_count > 0 ? 180 : 120;
    
    // Main box
    nodeGroup.append('rect')
        .attr('class', 'node-box')
        .attr('width', boxWidth)
        .attr('height', boxHeight)
        .attr('x', -boxWidth/2)
        .attr('y', -boxHeight/2)
        .attr('rx', 3)
        .attr('ry', 3);

    // Title bar
    nodeGroup.append('rect')
        .attr('class', 'node-title')
        .attr('width', boxWidth)
        .attr('height', 25)
        .attr('x', -boxWidth/2)
        .attr('y', -boxHeight/2)
        .attr('fill', node.role === 'master' ? '#ff4444' : '#33ff33')
        .attr('opacity', 0.3);

    // Node name
    nodeGroup.append('text')
        .attr('class', 'node-name')
        .attr('x', -boxWidth/2 + 10)
        .attr('y', -boxHeight/2 + 16)
        .text(`${node.info.hostname} (${node.role})`);

    // System info
    const systemInfo = nodeGroup.append('g')
        .attr('class', 'system-info')
        .attr('transform', `translate(${-boxWidth/2 + 10}, ${-boxHeight/2 + 40})`);

    systemInfo.append('text')
        .attr('y', 15)
        .text(`CPU: ${info.cpu_count} cores @ ${(info.cpu_freq/1000).toFixed(2)} GHz`);

    // Memory bar
    const memUsage = (info.total_memory - info.available_memory) / info.total_memory * 100;
    const memBar = systemInfo.append('g')
        .attr('transform', 'translate(0, 25)');

    memBar.append('text')
        .attr('y', 15)
        .text(`RAM: ${formatBytes(info.available_memory)} / ${formatBytes(info.total_memory)}`);

    memBar.append('rect')
        .attr('class', 'meter-bg')
        .attr('width', boxWidth - 20)
        .attr('height', 8)
        .attr('y', 20);

    memBar.append('rect')
        .attr('class', 'meter-fill')
        .attr('width', (boxWidth - 20) * (memUsage/100))
        .attr('height', 8)
        .attr('y', 20)
        .attr('fill', memUsage > 90 ? '#ff4444' : memUsage > 70 ? '#ffaa00' : '#33ff33');

    // GPU section
    if (info.gpu_count > 0) {
        const gpuSection = systemInfo.append('g')
            .attr('transform', 'translate(0, 70)');

        info.gpu_info.forEach((gpu, i) => {
            const gpuGroup = gpuSection.append('g')
                .attr('transform', `translate(0, ${i * 35})`);

            gpuGroup.append('text')
                .text(`GPU ${i+1}: ${gpu.name}`);

            const memUsage = gpu.current_memory / gpu.total_memory * 100;
            
            gpuGroup.append('rect')
                .attr('class', 'meter-bg')
                .attr('width', boxWidth - 20)
                .attr('height', 8)
                .attr('y', 15);

            gpuGroup.append('rect')
                .attr('class', 'meter-fill')
                .attr('width', (boxWidth - 20) * (memUsage/100))
                .attr('height', 8)
                .attr('y', 15)
                .attr('fill', '#2196F3');

            gpuGroup.append('text')
                .attr('x', 0)
                .attr('y', 35)
                .attr('class', 'gpu-memory')
                .style('font-size', '12px')
                .text(`Memory: ${formatBytes(gpu.current_memory)} / ${formatBytes(gpu.total_memory)}`);
        });
    }

    // Add connection status indicator
    nodeGroup.append('circle')
        .attr('class', 'status-indicator')
        .attr('r', 5)
        .attr('cx', boxWidth/2 - 15)
        .attr('cy', -boxHeight/2 + 12)
        .attr('fill', '#4CAF50');

    // Add ASCII decorations
    nodeGroup.append('text')
        .attr('class', 'ascii-decoration')
        .attr('x', -boxWidth/2)
        .attr('y', -boxHeight/2 - 10)
        .text(`+${'-'.repeat(Math.floor(boxWidth/8))}+`);
}

function updateVisualization(data) {
    if (!data || !data.nodes || !data.links) {
        console.warn('Invalid topology data received');
        return;
    }

    // Update statistics
    updateStats(data);

    // Clear previous content
    g.selectAll('*').remove();

    // Create links first (so they're behind nodes)
    const link = g.selectAll('.link')
        .data(data.links)
        .enter()
        .append('g')
        .attr('class', 'link');

    // Add dotted lines
    link.append('path')
        .attr('class', 'link-path')
        .attr('stroke-dasharray', '5,5');

    // Create nodes
    const node = g.selectAll('.node')
        .data(data.nodes)
        .enter()
        .append('g')
        .attr('class', d => `node ${d.role}`)
        .each(createNodeBox)
        .call(d3.drag()
            .on('start', dragstarted)
            .on('drag', dragged)
            .on('end', dragended));

    // Update force simulation
    simulation
        .nodes(data.nodes)
        .force('link').links(data.links);

    // Update positions on tick
    simulation.on('tick', () => {
        link.select('path')
            .attr('d', d => {
                const dx = d.target.x - d.source.x;
                const dy = d.target.y - d.source.y;
                return `M${d.source.x},${d.source.y}L${d.target.x},${d.target.y}`;
            });

        node.attr('transform', d => `translate(${d.x},${d.y})`);
    });

    simulation.alpha(1).restart();
}

// Add these styles
const extraStyles = `
    .node-box {
        fill: rgba(0, 0, 0, 0.8);
        stroke: #33ff33;
        stroke-width: 2px;
    }
    .meter-bg {
        fill: rgba(51, 255, 51, 0.1);
        stroke: #33ff33;
        stroke-width: 1px;
    }
    .meter-fill {
        opacity: 0.7;
    }
    .link-path {
        stroke: #33ff33;
        stroke-width: 2px;
    }
    .node text {
        fill: #33ff33;
        font-family: 'Courier New', monospace;
    }
    .ascii-decoration {
        fill: #33ff33;
        opacity: 0.5;
    }
`;

// Add the styles to the document
const styleSheet = document.createElement('style');
styleSheet.textContent = extraStyles;
document.head.appendChild(styleSheet);

// Drag functions
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

// Handle window resize
window.addEventListener('resize', () => {
    const width = window.innerWidth;
    const height = window.innerHeight;
    
    svg.attr('width', width)
        .attr('height', height);
        
    simulation.force('center', d3.forceCenter(width / 2, height / 2));
    simulation.alpha(1).restart();
});

// Add GPU utilization indicators
function addGPUMetrics(nodeEnter) {
    nodeEnter.each(function(d) {
        const node = d3.select(this);
        if (d.info.gpu_count > 0) {
            const gpuGroup = node.append('g')
                .attr('class', 'gpu-metrics')
                .attr('transform', 'translate(0, 45)');
            
            d.info.gpu_info.forEach((gpu, i) => {
                gpuGroup.append('rect')
                    .attr('x', -25 + (i * 12))
                    .attr('y', 0)
                    .attr('width', 10)
                    .attr('height', 15)
                    .attr('fill', '#2196F3')
                    .attr('stroke', '#fff')
                    .attr('stroke-width', 1);
            });
        }
    });
}

// Add system health indicators
function addHealthIndicator(nodeEnter) {
    nodeEnter.append('circle')
        .attr('class', 'health-indicator')
        .attr('r', 5)
        .attr('cx', 25)
        .attr('cy', -25)
        .attr('fill', d => {
            const memUsage = (d.info.total_memory - d.info.available_memory) / d.info.total_memory;
            return memUsage > 0.9 ? '#ff4444' : // Critical
                   memUsage > 0.7 ? '#ffaa00' : // Warning
                   '#4CAF50'; // Healthy
        });
}

// Show detailed metrics panel
function showDetailedMetrics(node) {
    const detailsPanel = d3.select('body')
        .append('div')
        .attr('class', 'details-panel')
        .style('position', 'fixed')
        .style('right', '20px')
        .style('top', '50%')
        .style('transform', 'translateY(-50%)')
        .style('background', 'rgba(0, 0, 0, 0.9)')
        .style('padding', '20px')
        .style('border-radius', '10px')
        .style('z-index', 1000);
    
    // Add close button
    detailsPanel.append('div')
        .style('text-align', 'right')
        .append('button')
        .text('×')
        .on('click', () => detailsPanel.remove());
    
    // Add metrics
    const metrics = detailsPanel.append('div')
        .style('margin-top', '10px');
    
    // Add real-time updates
    function updateMetrics() {
        metrics.html(`
            <h3>Node Metrics: ${node.id}</h3>
            <div class="metric-group">
                <h4>CPU Usage</h4>
                <div class="progress-bar">
                    <div style="width: ${node.info.cpu_percent}%"></div>
                </div>
            </div>
            <div class="metric-group">
                <h4>Memory Usage</h4>
                <div class="progress-bar">
                    <div style="width: ${(node.info.total_memory - node.info.available_memory) / node.info.total_memory * 100}%"></div>
                </div>
            </div>
            ${node.info.gpu_info.map((gpu, i) => `
                <div class="metric-group">
                    <h4>GPU ${i + 1}: ${gpu.name}</h4>
                    <div class="progress-bar">
                        <div style="width: ${gpu.utilization || 0}%"></div>
                    </div>
                </div>
            `).join('')}
        `);
    }
    
    updateMetrics();
    const updateInterval = setInterval(updateMetrics, 1000);
    
    // Cleanup on close
    detailsPanel.on('remove', () => clearInterval(updateInterval));
}