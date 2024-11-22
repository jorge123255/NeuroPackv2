// Set up the D3 visualization
const width = window.innerWidth;
const height = window.innerHeight;

const svg = d3.select('#topology-container')
    .append('svg')
    .attr('width', width)
    .attr('height', height);

// Add zoom behavior
const g = svg.append('g');
const zoom = d3.zoom()
    .on('zoom', (event) => {
        g.attr('transform', event.transform);
    });
svg.call(zoom);

// Set up force simulation
const simulation = d3.forceSimulation()
    .force('link', d3.forceLink().id(d => d.id).distance(100))
    .force('charge', d3.forceManyBody().strength(-300))
    .force('center', d3.forceCenter(width / 2, height / 2));

// WebSocket connection
const ws = new WebSocket(`ws://${window.location.hostname}:8765`);

let nodes = [];
let links = [];

ws.onmessage = function(event) {
    const data = JSON.parse(event.data);
    
    // Update nodes and links based on received data
    nodes = data.nodes || [];
    links = data.links || [];

    // Update visualization
    updateVisualization();
};

function updateVisualization() {
    // Update links
    const link = g.selectAll('.link')
        .data(links, d => `${d.source.id || d.source}-${d.target.id || d.target}`);

    link.exit().remove();

    const linkEnter = link.enter()
        .append('line')
        .attr('class', 'link');

    // Update nodes
    const node = g.selectAll('.node')
        .data(nodes, d => d.id);

    node.exit().remove();

    const nodeEnter = node.enter()
        .append('g')
        .attr('class', 'node')
        .call(d3.drag()
            .on('start', dragstarted)
            .on('drag', dragged)
            .on('end', dragended));

    nodeEnter.append('circle')
        .attr('r', 20)
        .attr('fill', d => d.role === 'master' ? '#ff4444' : '#4CAF50');

    nodeEnter.append('text')
        .attr('dy', 30)
        .attr('text-anchor', 'middle')
        .text(d => d.id);

    // Update simulation
    simulation
        .nodes(nodes)
        .on('tick', () => {
            g.selectAll('.link')
                .attr('x1', d => d.source.x)
                .attr('y1', d => d.source.y)
                .attr('x2', d => d.target.x)
                .attr('y2', d => d.target.y);

            g.selectAll('.node')
                .attr('transform', d => `translate(${d.x},${d.y})`);
        });

    simulation.force('link').links(links);
    simulation.alpha(1).restart();
}

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