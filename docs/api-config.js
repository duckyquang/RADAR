// API Configuration
// Update this URL after deploying backend to Railway/Render
const API_BASE = process.env.NODE_ENV === 'production' 
  ? 'https://radar-backend-xxxxx.railway.app'  // Replace with your Railway URL
  : 'http://localhost:8000';

window.API_CONFIG = { base: API_BASE };
