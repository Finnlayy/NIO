const { execSync } = require('child_process');
try {
  execSync('make ui-test', { stdio: 'inherit' });
} catch (e) {
  process.exit(1);
}
