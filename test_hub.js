const { getTelemetryHub } = require('./frontend/src/server/telemetryBridge');
// Just checking if process listeners are there
console.log(process.listeners('SIGINT').length);
