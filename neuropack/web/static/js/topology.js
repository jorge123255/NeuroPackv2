const ws = new WebSocket(`ws://${window.location.hostname}:8765`);

ws.onmessage = function(event) {
    console.log('Received:', event.data);  // Add this line to debug
    // Update visualization with received data
}; 