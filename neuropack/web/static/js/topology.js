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

// Enhanced visualization update
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

    // Update model panel
    updateModelPanel(data);
    
    // Start real-time updates
    startRealtimeUpdates();
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