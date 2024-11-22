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

// Update the force simulation setup
const simulation = d3.forceSimulation()
    .force('link', d3.forceLink().id(d => d.id).distance(300))
    .force('charge', d3.forceManyBody().strength(-2000))
    .force('collision', d3.forceCollide().radius(200))
    .force('x', d3.forceX(width / 2).strength(0.5))
    .force('y', d3.forceY(height / 2).strength(0.5));

// Update the WebSocket connection to use the correct port
const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
const wsUrl = `${wsProtocol}//${window.location.hostname}:${window.location.port}/ws`;
console.log('Connecting to WebSocket:', wsUrl);

const ws = new WebSocket(wsUrl);

ws.onopen = () => {
    console.log('WebSocket connected');
    d3.select('.connection-status')
        .style('color', '#4CAF50')
        .text('● Connected to server');
};

ws.onclose = () => {
    console.error('WebSocket disconnected');
    d3.select('.connection-status')
        .style('color', '#ff4444')
        .text('● Disconnected from server');
};

ws.onerror = (error) => {
    console.error('WebSocket error:', error);
};

ws.onmessage = function(event) {
    console.log('Received topology data:', event.data);
    try {
        const data = JSON.parse(event.data);
        console.log('Parsed topology data:', data);
        if (data.nodes && data.links) {
            updateVisualization(data);
        } else {
            console.error('Invalid topology data format:', data);
        }
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

// Add terminal interface
const terminal = d3.select('body')
    .append('div')
    .attr('class', 'terminal')
    .style('position', 'fixed')
    .style('bottom', '20px')
    .style('left', '20px')
    .style('width', '600px')
    .style('background', 'rgba(0, 0, 0, 0.9)')
    .style('border', '1px solid #33ff33')
    .style('padding', '10px')
    .style('font-family', 'Courier New, monospace')
    .style('color', '#33ff33')
    .style('z-index', '1000');

terminal.append('div')
    .attr('class', 'terminal-header')
    .html(`
        +${'-'.repeat(58)}+
        |                    NeuroPack Terminal                    |
        +${'-'.repeat(58)}+
    `.replace(/\n/g, '<br>'));

const terminalOutput = terminal.append('div')
    .attr('class', 'terminal-output')
    .style('max-height', '200px')
    .style('overflow-y', 'auto')
    .style('margin', '10px 0');

const terminalInput = terminal.append('div')
    .attr('class', 'terminal-input')
    .style('display', 'flex');

terminalInput.append('span')
    .text('> ')
    .style('color', '#33ff33')
    .style('margin-right', '5px');

const input = terminalInput.append('input')
    .attr('type', 'text')
    .style('background', 'transparent')
    .style('border', 'none')
    .style('color', '#33ff33')
    .style('font-family', 'Courier New, monospace')
    .style('width', '100%')
    .style('outline', 'none');

// Terminal command handling
input.on('keypress', function(event) {
    if (event.key === 'Enter') {
        const command = this.value;
        processCommand(command);
        this.value = '';
    }
});

function processCommand(command) {
    terminalOutput.append('div')
        .html(`> ${command}`);
    
    switch(command.toLowerCase()) {
        case 'help':
            showHelp();
            break;
        case 'status':
            showClusterStatus();
            break;
        case 'models':
            showModels();
            break;
        case 'clear':
            terminalOutput.html('');
            break;
        default:
            terminalOutput.append('div')
                .style('color', '#ff4444')
                .text('Unknown command. Type "help" for available commands.');
    }
    
    // Scroll to bottom
    terminalOutput.node().scrollTop = terminalOutput.node().scrollHeight;
}

function showHelp() {
    terminalOutput.append('div')
        .html(`
            Available Commands:
            - help    : Show this help message
            - status  : Show cluster status
            - models  : List available models
            - clear   : Clear terminal
        `);
}

// Add model information display
const modelPanel = d3.select('body')
    .append('div')
    .attr('class', 'model-panel')
    .style('position', 'fixed')
    .style('left', '20px')
    .style('top', '100px')
    .style('background', 'rgba(0, 0, 0, 0.9)')
    .style('border', '1px solid #33ff33')
    .style('padding', '15px')
    .style('font-family', 'Courier New, monospace')
    .style('color', '#33ff33');

function updateModelPanel(data) {
    const allModels = new Set();
    data.nodes.forEach(node => {
        if (node.info.supported_models) {
            node.info.supported_models.forEach(model => allModels.add(model));
        }
    });

    modelPanel.html(`
        +${'-'.repeat(30)}+
        |      Available Models      |
        +${'-'.repeat(30)}+
        ${Array.from(allModels).map(model => `| ${model.padEnd(28)} |`).join('\n')}
        +${'-'.repeat(30)}+
    `.replace(/\n/g, '<br>'));
}

// Enhanced node box creation
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

    // Add model information
    if (node.info.loaded_models) {
        const modelSection = systemInfo.append('g')
            .attr('transform', `translate(0, ${info.gpu_count > 0 ? 180 : 120})`);

        modelSection.append('text')
            .text('Loaded Models:');

        Object.entries(node.info.loaded_models).forEach(([name, model], i) => {
            modelSection.append('text')
                .attr('y', (i + 1) * 20)
                .text(`${name} (${model.type})`);
        });
    }

    // Add real-time metrics
    const metricsSection = nodeGroup.append('g')
        .attr('class', 'metrics')
        .attr('transform', `translate(${boxWidth/2 - 60}, -${boxHeight/2 + 15})`);

    // CPU usage indicator
    const cpuMeter = metricsSection.append('g');
    cpuMeter.append('rect')
        .attr('class', 'meter-bg')
        .attr('width', 50)
        .attr('height', 8);

    cpuMeter.append('rect')
        .attr('class', 'meter-fill cpu-meter')
        .attr('width', 0)
        .attr('height', 8);

    // Add ASCII decorations
    const decorations = [
        { x: -boxWidth/2, y: -boxHeight/2, char: '+' },
        { x: boxWidth/2, y: -boxHeight/2, char: '+' },
        { x: -boxWidth/2, y: boxHeight/2, char: '+' },
        { x: boxWidth/2, y: boxHeight/2, char: '+' }
    ];

    decorations.forEach(d => {
        nodeGroup.append('text')
            .attr('class', 'ascii-decoration')
            .attr('x', d.x)
            .attr('y', d.y)
            .text(d.char);
    });

    addPerformanceGraphs(nodeGroup, node);
    addModelLoadingStatus(nodeGroup, node);
    addResourceMeters(nodeGroup, node);
    
    // Start health monitoring
    updateNodeHealth(nodeGroup);
}

// Add performance monitoring graphs
function addPerformanceGraphs(nodeGroup, node) {
    const graphGroup = nodeGroup.append('g')
        .attr('class', 'performance-graphs')
        .attr('transform', 'translate(-120, 80)');

    // CPU Usage Graph
    const cpuGraph = graphGroup.append('g')
        .attr('class', 'cpu-graph');
    
    const cpuData = new Array(30).fill(0);
    
    cpuGraph.append('rect')
        .attr('class', 'graph-bg')
        .attr('width', 100)
        .attr('height', 20);
        
    const cpuLine = d3.line()
        .x((d, i) => i * (100/30))
        .y(d => 20 - (d * 20/100));
        
    cpuGraph.append('path')
        .attr('class', 'cpu-line')
        .attr('d', cpuLine(cpuData))
        .style('stroke', '#33ff33')
        .style('fill', 'none');

    // Memory Usage Graph
    const memGraph = graphGroup.append('g')
        .attr('class', 'mem-graph')
        .attr('transform', 'translate(0, 30)');
        
    // Similar setup for memory graph...
}

// Add real-time model loading indicators
function addModelLoadingStatus(nodeGroup, node) {
    const modelGroup = nodeGroup.append('g')
        .attr('class', 'model-status')
        .attr('transform', 'translate(-120, -60)');

    Object.entries(node.info.loaded_models || {}).forEach(([name, model], i) => {
        const status = modelGroup.append('g')
            .attr('transform', `translate(0, ${i * 20})`);
            
        status.append('circle')
            .attr('r', 4)
            .attr('fill', model.loaded ? '#4CAF50' : '#ff4444');
            
        status.append('text')
            .attr('x', 10)
            .attr('class', 'model-name')
            .text(name);
    });
}

// Add network traffic visualization
function addNetworkTraffic(link) {
    const particles = link.append('g')
        .attr('class', 'traffic-particles')
        .selectAll('circle')
        .data(d3.range(5))
        .enter()
        .append('circle')
        .attr('r', 2)
        .attr('fill', '#33ff33');
        
    function animateParticles() {
        particles.each(function(d) {
            d3.select(this)
                .attr('opacity', 1)
                .transition()
                .duration(2000)
                .attr('transform', `translate(${Math.random() * 100}, 0)`)
                .attr('opacity', 0)
                .on('end', animateParticles);
        });
    }
    
    animateParticles();
}

// Add resource utilization meters
function addResourceMeters(nodeGroup, node) {
    const meterGroup = nodeGroup.append('g')
        .attr('class', 'resource-meters')
        .attr('transform', 'translate(60, -40)');

    // CPU Meter
    const cpuMeter = meterGroup.append('g')
        .attr('class', 'cpu-meter');
        
    cpuMeter.append('rect')
        .attr('class', 'meter-bg')
        .attr('width', 60)
        .attr('height', 8);
        
    cpuMeter.append('rect')
        .attr('class', 'meter-fill')
        .attr('width', `${node.metrics?.cpu_usage || 0}%`)
        .attr('height', 8);

    // Memory Meter
    const memMeter = meterGroup.append('g')
        .attr('class', 'memory-meter')
        .attr('transform', 'translate(0, 15)');
        
    // Similar setup for memory meter...
}

// Add node health monitoring
function updateNodeHealth(node) {
    const healthStatus = calculateNodeHealth(node);
    
    node.select('.health-indicator')
        .transition()
        .duration(500)
        .attr('fill', healthStatus.color)
        .attr('r', healthStatus.critical ? 8 : 5);
        
    if (healthStatus.critical) {
        node.select('.node-box')
            .transition()
            .duration(500)
            .style('stroke', '#ff4444')
            .transition()
            .duration(500)
            .style('stroke', '#33ff33')
            .on('end', () => updateNodeHealth(node));
    }
}

function calculateNodeHealth(node) {
    const metrics = node.metrics || {};
    const critical = 
        metrics.cpu_usage > 90 ||
        metrics.memory_usage > 90 ||
        (node.info.gpu_count > 0 && node.info.gpu_info.some(gpu => gpu.utilization > 95));
        
    return {
        critical,
        color: critical ? '#ff4444' : 
               metrics.cpu_usage > 70 ? '#ffaa00' : '#4CAF50'
    };
}

// Add real-time updates
function startRealtimeUpdates() {
    setInterval(() => {
        d3.selectAll('.cpu-meter')
            .transition()
            .duration(1000)
            .attr('width', () => Math.random() * 50);
    }, 2000);
}

// Update node positioning function
function initializeNodePositions(nodes) {
    const masterNode = nodes.find(n => n.role === 'master');
    const workerNodes = nodes.filter(n => n.role !== 'master');
    
    if (masterNode) {
        // Fix master node in center
        masterNode.fx = width / 2;
        masterNode.fy = height / 2;
        
        // Position worker nodes in a hexagonal pattern around master
        const radius = 350; // Distance from center
        const angleStep = (2 * Math.PI) / Math.max(6, workerNodes.length);
        
        workerNodes.forEach((node, i) => {
            const angle = i * angleStep;
            // Fix worker nodes in position
            node.fx = width / 2 + radius * Math.cos(angle);
            node.fy = height / 2 + radius * Math.sin(angle);
        });
    }
}

// Create a more terminal-style layout
function createTerminalLayout(data) {
    // Clear previous content
    g.selectAll('*').remove();

    const masterNode = data.nodes.find(n => n.role === 'master');
    const workerNodes = data.nodes.filter(n => n.role !== 'master');

    // Create ASCII art header
    const header = g.append('g')
        .attr('class', 'cluster-header')
        .attr('transform', `translate(${width/2}, 60)`);

    header.append('text')
        .attr('text-anchor', 'middle')
        .attr('class', 'cluster-title')
        .text(`Exo Cluster (${data.nodes.length} nodes)`);

    // Create master node box
    if (masterNode) {
        const masterBox = createNodeBox(masterNode, width/2, 150);
        
        // Create connection lines to worker nodes
        workerNodes.forEach((worker, i) => {
            const y = 300 + i * 180;
            const workerBox = createNodeBox(worker, width/2, y);
            
            // Create ASCII connection line
            createConnectionLine(width/2, 200, width/2, y - 50);
        });
    }

    // Add cluster stats
    createClusterStats(data, 20, 20);
}

function createNodeBox(node, x, y) {
    const boxGroup = g.append('g')
        .attr('class', `node ${node.role}`)
        .attr('transform', `translate(${x}, ${y})`);

    const info = node.info;
    const lines = [
        `+${'-'.repeat(58)}+`,
        `| ${node.id.padEnd(56)} |`,
        `| ${info.hostname} (${node.role})${' '.repeat(45-info.hostname.length)} |`,
        `+${'-'.repeat(58)}+`,
        `| CPU: ${info.cpu_count} cores @ ${(info.cpu_freq/1000).toFixed(2)} GHz${' '.repeat(35)} |`,
        `| RAM: ${formatBytes(info.available_memory)} / ${formatBytes(info.total_memory)}${' '.repeat(25)} |`
    ];

    // Add GPU information if available
    if (info.gpu_count > 0) {
        info.gpu_info.forEach((gpu, i) => {
            lines.push(`| GPU ${i+1}: ${gpu.name}${' '.repeat(Math.max(0, 53-gpu.name.length))} |`);
            // Add GPU memory bar
            const memUsage = gpu.current_memory / gpu.total_memory * 100;
            const barWidth = 40;
            const filledChars = Math.floor(memUsage * barWidth / 100);
            const bar = '[' + '='.repeat(filledChars) + ' '.repeat(barWidth - filledChars) + ']';
            lines.push(`| Memory: ${bar} ${memUsage.toFixed(1)}%${' '.repeat(8)} |`);
        });
    }

    lines.push(`+${'-'.repeat(58)}+`);

    // Add status indicator
    const statusColor = node.role === 'master' ? '#ff4444' : '#4CAF50';
    boxGroup.append('circle')
        .attr('r', 5)
        .attr('cx', -140)
        .attr('cy', 0)
        .attr('fill', statusColor);

    // Add box text
    lines.forEach((line, i) => {
        boxGroup.append('text')
            .attr('x', -130)
            .attr('y', (i - lines.length/2) * 20)
            .attr('class', 'node-text')
            .text(line);
    });

    return boxGroup;
}

function createConnectionLine(x1, y1, x2, y2) {
    const points = [];
    const dx = x2 - x1;
    const dy = y2 - y1;
    const steps = Math.abs(dy) / 20;

    for (let i = 0; i <= steps; i++) {
        points.push([x1, y1 + (dy * i / steps)]);
    }

    const line = g.append('g').attr('class', 'connection');

    // Create dotted line effect using ASCII characters
    points.forEach((point, i) => {
        if (i % 2 === 0) {
            line.append('text')
                .attr('x', point[0])
                .attr('y', point[1])
                .attr('text-anchor', 'middle')
                .attr('class', 'connection-text')
                .text('|');
        }
    });
}

function createClusterStats(data, x, y) {
    const totalCPUs = data.nodes.reduce((acc, n) => acc + n.info.cpu_count, 0);
    const totalGPUs = data.nodes.reduce((acc, n) => acc + n.info.gpu_count, 0);
    const totalMemory = data.nodes.reduce((acc, n) => acc + n.info.total_memory, 0);

    const statsGroup = g.append('g')
        .attr('class', 'cluster-stats')
        .attr('transform', `translate(${x}, ${y})`);

    const lines = [
        `+${'-'.repeat(30)}+`,
        '| Cluster Statistics        |',
        `+${'-'.repeat(30)}+`,
        `| Nodes: ${data.nodes.length.toString().padEnd(20)} |`,
        `| CPUs:  ${totalCPUs.toString().padEnd(20)} |`,
        `| GPUs:  ${totalGPUs.toString().padEnd(20)} |`,
        `| RAM:   ${formatBytes(totalMemory).padEnd(20)} |`,
        `+${'-'.repeat(30)}+`
    ];

    lines.forEach((line, i) => {
        statsGroup.append('text')
            .attr('y', i * 20)
            .attr('class', 'stats-text')
            .text(line);
    });
}

// Update visualization function
function updateVisualization(data) {
    if (!data || !data.nodes || !data.links) {
        console.warn('Invalid topology data received');
        return;
    }

    createTerminalLayout(data);
}

// Add styles
const terminalStyles = `
    .node-text {
        font-family: 'Courier New', monospace;
        fill: #33ff33;
        font-size: 14px;
    }
    .connection-text {
        font-family: 'Courier New', monospace;
        fill: #33ff33;
        font-size: 14px;
    }
    .stats-text {
        font-family: 'Courier New', monospace;
        fill: #33ff33;
        font-size: 14px;
    }
    .cluster-title {
        font-family: 'Courier New', monospace;
        fill: #33ff33;
        font-size: 18px;
    }
`;

const styleSheet = document.createElement('style');
styleSheet.textContent = terminalStyles;
document.head.appendChild(styleSheet);

// Remove drag-related functions and simplify the simulation
simulation.on('tick', () => {
    // No tick updates needed as nodes are fixed
});

// Update window resize handler
window.addEventListener('resize', () => {
    const width = window.innerWidth;
    const height = window.innerHeight;
    
    svg.attr('width', width)
        .attr('height', height);
    
    // Recalculate fixed positions on resize
    const nodes = simulation.nodes();
    initializeNodePositions(nodes);
    
    // Update node and link positions
    g.selectAll('.node')
        .attr('transform', d => `translate(${d.fx},${d.fy})`);
        
    g.selectAll('.link')
        .attr('d', d => {
            const dx = d.target.fx - d.source.fx;
            const dy = d.target.fy - d.source.fy;
            const dr = Math.sqrt(dx * dx + dy * dy) * 1.2;
            return `M${d.source.fx},${d.source.fy}A${dr},${dr} 0 0,1 ${d.target.fx},${d.target.fy}`;
        });
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

// Add keyboard shortcuts
document.addEventListener('keydown', (event) => {
    if (event.key === 't') {
        terminal.style('display', 
            terminal.style('display') === 'none' ? 'block' : 'none');
    }
});

// Add these styles
const additionalStyles = `
    .terminal-output div {
        margin: 2px 0;
    }
    .meter-bg {
        fill: rgba(51, 255, 51, 0.1);
        stroke: #33ff33;
    }
    .meter-fill {
        fill: #33ff33;
    }
    .ascii-decoration {
        fill: #33ff33;
        font-family: 'Courier New', monospace;
    }
    .model-panel {
        max-height: 400px;
        overflow-y: auto;
    }
`;

// Add the styles to the document
const additionalStyleSheet = document.createElement('style');
additionalStyleSheet.textContent = additionalStyles;
document.head.appendChild(additionalStyleSheet);

// Add a context menu for node actions
function addContextMenu(node) {
    node.on('contextmenu', (event, d) => {
        event.preventDefault();
        
        const menu = d3.select('body')
            .append('div')
            .attr('class', 'context-menu')
            .style('position', 'absolute')
            .style('left', `${event.pageX}px`)
            .style('top', `${event.pageY}px`)
            .style('background', 'rgba(0, 0, 0, 0.9)')
            .style('border', '1px solid #33ff33')
            .style('padding', '5px')
            .style('z-index', 1000);

        menu.append('div')
            .text('Reset Position')
            .style('cursor', 'pointer')
            .style('padding', '5px')
            .on('click', () => {
                d.fx = null;
                d.fy = null;
                simulation.alpha(0.3).restart();
                menu.remove();
            });

        menu.append('div')
            .text('Pin/Unpin')
            .style('cursor', 'pointer')
            .style('padding', '5px')
            .on('click', () => {
                if (d.fx === null) {
                    d.fx = d.x;
                    d.fy = d.y;
                } else {
                    d.fx = null;
                    d.fy = null;
                }
                simulation.alpha(0.3).restart();
                menu.remove();
            });

        // Close menu on click outside
        d3.select('body').on('click.context-menu', () => {
            menu.remove();
            d3.select('body').on('click.context-menu', null);
        });
    });
}

// Add these style updates
const enhancedStyles = `
    .cpu-line {
        stroke-width: 2px;
    }
    .graph-bg {
        fill: rgba(51, 255, 51, 0.1);
        stroke: #33ff33;
    }
    .traffic-particles circle {
        filter: blur(1px);
    }
    .model-name {
        font-size: 12px;
        fill: #33ff33;
    }
    .critical-alert {
        animation: pulse 1s infinite;
    }
    @keyframes pulse {
        0% { opacity: 1; }
        50% { opacity: 0.5; }
        100% { opacity: 1; }
    }
`;

// Update the node creation to include new features
function createNodeBox(node) {
    const nodeGroup = d3.select(this);
    
    // ... existing node box creation code ...
    
    addPerformanceGraphs(nodeGroup, node);
    addModelLoadingStatus(nodeGroup, node);
    addResourceMeters(nodeGroup, node);
    
    // Start health monitoring
    updateNodeHealth(nodeGroup);
}