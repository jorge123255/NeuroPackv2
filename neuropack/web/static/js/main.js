const ws = new WebSocket(`ws://${window.location.hostname}:8765`);

ws.onopen = function() {
    console.log('WebSocket Connected');
};

ws.onerror = function(error) {
    console.error('WebSocket Error:', error);
};

ws.onclose = function() {
    console.log('WebSocket Disconnected');
    // Implement reconnection logic if needed
    setTimeout(() => {
        // Attempt to reconnect
    }, 1000);
}; 