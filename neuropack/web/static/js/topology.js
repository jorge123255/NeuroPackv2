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
        
        // Initialize node positions on first update
        if (data.nodes && !nodes.length) {
            initializeNodePositions(data.nodes);
        }
        
        // Update visualization
        if (data.nodes && data.links) {
            nodes = data.nodes;
            links = data.links;
            updateVisualization(data);
            updateStats(data);
            updateModelPanel(data);
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
    
    // Main box outline
    const boxOutline = [
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
            boxOutline.push(`| GPU ${i+1}: ${gpu.name}${' '.repeat(Math.max(0, 53-gpu.name.length))} |`);
            const memUsage = gpu.current_memory / gpu.total_memory * 100;
            const barWidth = 40;
            const filledChars = Math.floor(memUsage * barWidth / 100);
            const bar = '[' + '='.repeat(filledChars) + ' '.repeat(barWidth - filledChars) + ']';
            boxOutline.push(`| Memory: ${bar} ${memUsage.toFixed(1)}%${' '.repeat(8)} |`);
        });
    }

    boxOutline.push(`+${'-'.repeat(58)}+`);

    // Create the box
    const box = nodeGroup.append('g')
        .attr('class', 'node-box');

    // Add box text lines
    boxOutline.forEach((line, i) => {
        box.append('text')
            .attr('x', -130)
            .attr('y', (i - boxOutline.length/2) * 20)
            .attr('class', 'node-text')
            .text(line);
    });

    // Add status indicator
    const statusColor = node.role === 'master' ? '#ff4444' : '#4CAF50';
    box.append('circle')
        .attr('r', 5)
        .attr('cx', -140)
        .attr('cy', -boxOutline.length/2 * 20 + 15)
        .attr('fill', statusColor);

    // Add metrics bars
    const metricsGroup = box.append('g')
        .attr('transform', `translate(-120, ${boxOutline.length/2 * 20 + 10})`);

    // CPU usage bar
    addMetricBar(metricsGroup, 'CPU', node.metrics?.cpu_usage || 0, 0);
    
    // Memory usage bar
    const memUsage = (info.total_memory - info.available_memory) / info.total_memory * 100;
    addMetricBar(metricsGroup, 'MEM', memUsage, 25);

    // Add hover interaction
    box.on('mouseover', () => showTooltip(node))
       .on('mouseout', hideTooltip);
}

// Helper function to add metric bars
function addMetricBar(group, label, value, yOffset) {
    const barWidth = 100;
    const barHeight = 10;

    group.append('text')
        .attr('x', -30)
        .attr('y', yOffset + 8)
        .attr('class', 'metric-label')
        .text(label);

    group.append('rect')
        .attr('x', 0)
        .attr('y', yOffset)
        .attr('width', barWidth)
        .attr('height', barHeight)
        .attr('class', 'metric-bar-bg');

    group.append('rect')
        .attr('x', 0)
        .attr('y', yOffset)
        .attr('width', value * barWidth / 100)
        .attr('height', barHeight)
        .attr('class', 'metric-bar-fill')
        .attr('fill', value > 90 ? '#ff4444' : value > 70 ? '#ffaa00' : '#33ff33');

    group.append('text')
        .attr('x', barWidth + 10)
        .attr('y', yOffset + 8)
        .attr('class', 'metric-value')
        .text(`${value.toFixed(1)}%`);
}

// Update the visualization function
function updateVisualization(data) {
    if (!data || !data.nodes || !data.links) {
        console.warn('Invalid topology data received');
        return;
    }

    // Update nodes
    const nodeElements = g.selectAll('.node')
        .data(data.nodes, d => d.id);

    // Remove old nodes
    nodeElements.exit().remove();

    // Add new nodes with fixed positions
    const nodeEnter = nodeElements.enter()
        .append('g')
        .attr('class', 'node');

    // Position nodes
    const masterNode = data.nodes.find(n => n.role === 'master');
    const workerNodes = data.nodes.filter(n => n.role !== 'master');

    if (masterNode) {
        masterNode.fx = width / 2;
        masterNode.fy = height / 3;
    }

    // Position worker nodes in a semi-circle below master
    workerNodes.forEach((node, i) => {
        const angle = (Math.PI / (workerNodes.length + 1)) * (i + 1);
        const radius = 300;
        node.fx = width/2 + radius * Math.cos(angle);
        node.fy = height/3 + radius * Math.sin(angle);
    });

    // Create node boxes
    nodeElements.merge(nodeEnter).each(createNodeBox);

    // Update links
    const linkElements = g.selectAll('.link')
        .data(data.links, d => `${d.source}-${d.target}`);

    // Remove old links
    linkElements.exit().remove();

    // Add new links with ASCII-style
    linkElements.enter()
        .append('path')
        .attr('class', 'link')
        .attr('d', d => {
            const sourceNode = data.nodes.find(n => n.id === d.source);
            const targetNode = data.nodes.find(n => n.id === d.target);
            if (sourceNode && targetNode) {
                return createASCIILink(sourceNode.fx, sourceNode.fy, targetNode.fx, targetNode.fy);
            }
            return '';
        });

    // Update stats and model panel
    updateStats(data);
    updateModelPanel(data);
}

// Create ASCII-style link path
function createASCIILink(x1, y1, x2, y2) {
    const dx = x2 - x1;
    const dy = y2 - y1;
    const dr = Math.sqrt(dx * dx + dy * dy) * 1.2;
    return `M${x1},${y1}A${dr},${dr} 0 0,1 ${x2},${y2}`;
}

// Add these styles
const additionalStyles = `
    .node-text {
        font-family: 'Courier New', monospace;
        fill: #33ff33;
        font-size: 12px;
    }
    .link {
        stroke: #33ff33;
        stroke-width: 2px;
        stroke-dasharray: 5,5;
    }
    .metric-bar-bg {
        fill: rgba(51, 255, 51, 0.1);
        stroke: #33ff33;
        stroke-width: 1px;
    }
    .metric-bar-fill {
        fill: #33ff33;
    }
    .metric-label, .metric-value {
        font-family: 'Courier New', monospace;
        fill: #33ff33;
        font-size: 12px;
    }
`;

// Add the styles
const styleSheet = document.createElement('style');
styleSheet.textContent = additionalStyles;
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