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

    const masterNode = data.nodes.find(n => n.role === 'master');
    const workerNodes = data.nodes.filter(n => n.role !== 'master');

    // Set up dimensions
    const centerX = width / 2;
    const masterY = height * 0.2;
    const workerY = height * 0.6;

    // Create master node
    if (masterNode) {
        const masterGroup = g.append('g')
            .attr('class', 'node master')
            .attr('transform', `translate(${centerX}, ${masterY})`);

        createNodeBox.call(masterGroup.node(), masterNode);
    }

    // Position worker nodes
    workerNodes.forEach((node, i) => {
        const x = centerX + (i - (workerNodes.length - 1) / 2) * 300;
        const workerGroup = g.append('g')
            .attr('class', 'node worker')
            .attr('transform', `translate(${x}, ${workerY})`);

        createNodeBox.call(workerGroup.node(), node);

        // Create connection to master
        if (masterNode) {
            createConnection(g, 
                {x: centerX, y: masterY}, 
                {x: x, y: workerY}, 
                node.id);
        }
    });

    // Update stats
    updateStats(data);
}

function createNodeBox(node) {
    const g = d3.select(this);
    const info = node.info;

    // Create ASCII box
    const lines = [
        `+${'-'.repeat(58)}+`,
        `| ${node.id.padEnd(56)} |`,
        `| ${info.hostname} (${node.role})${' '.repeat(45-info.hostname.length)} |`,
        `+${'-'.repeat(58)}+`,
        `| CPU: ${info.cpu_count} cores @ ${(info.cpu_freq/1000).toFixed(2)} GHz${' '.repeat(35)} |`,
        `| RAM: ${formatBytes(info.available_memory)} / ${formatBytes(info.total_memory)}${' '.repeat(25)} |`
    ];

    if (info.gpu_count > 0) {
        info.gpu_info.forEach((gpu, i) => {
            lines.push(`| GPU ${i+1}: ${gpu.name}${' '.repeat(Math.max(0, 53-gpu.name.length))} |`);
            lines.push(`| Memory: [ ] ${formatBytes(gpu.current_memory)} / ${formatBytes(gpu.total_memory)}${' '.repeat(20)} |`);
        });
    }

    lines.push(`+${'-'.repeat(58)}+`);

    lines.forEach((line, i) => {
        g.append('text')
            .attr('class', 'node-text')
            .attr('x', 0)
            .attr('y', i * 20)
            .attr('text-anchor', 'middle')
            .text(line);
    });
}

function createConnection(g, source, target, nodeId) {
    const linkGroup = g.append('g').attr('class', 'link');
    
    // Draw connection line with dots
    const numDots = 20;
    for (let i = 0; i <= numDots; i++) {
        const t = i / numDots;
        const x = source.x + (target.x - source.x) * t;
        const y = source.y + (target.y - source.y) * t;
        
        linkGroup.append('text')
            .attr('x', x)
            .attr('y', y)
            .attr('class', 'connection-dot')
            .text('·')
            .style('animation', `blink ${1 + Math.random()}s infinite`);
    }
}

// Initialize WebSocket connection
connectWebSocket();

// Helper function to format bytes
function formatBytes(bytes) {
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    if (bytes === 0) return '0 B';
    const i = parseInt(Math.floor(Math.log(bytes) / Math.log(1024)));
    return Math.round(bytes / Math.pow(1024, i), 2) + ' ' + sizes[i];
}