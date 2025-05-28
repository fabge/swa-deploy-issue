# Welcome to MkDocs

<div id="stream-container"></div>

<button id="stream-button" onclick="fetchStreamingData()">Start Stream</button>

<script>
async function fetchStreamingData() {
  const container = document.getElementById('stream-container');
  container.innerHTML = '';

  // Determine API URL based on current hostname
  const isLocalhost = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
  const apiUrl = isLocalhost ? 'http://localhost:7071/api/message' : '/api/message';

  try {
    const response = await fetch(apiUrl);

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();

    while (true) {
      const { value, done } = await reader.read();

      if (done) break;

      const text = decoder.decode(value, { stream: true });
      const div = document.createElement('div');
      div.textContent = text;
      container.appendChild(div);
    }
  } catch (error) {
    console.error('Error:', error);
    container.innerHTML = `<div class="error">Error: ${error.message}</div>`;
  }
}
</script>

<style>
#stream-container {
  min-height: 100px;
  max-height: 400px;
  overflow-y: auto;
  border: 1px solid #ddd;
  padding: 10px;
  margin-bottom: 10px;
  background-color: #f9f9f9;
}
.error {
  color: red;
}
#stream-button {
  background-color: #4CAF50;
  color: white;
  border: none;
  padding: 10px 20px;
  text-align: center;
  text-decoration: none;
  display: inline-block;
  font-size: 16px;
  margin: 10px 0;
  cursor: pointer;
  border-radius: 4px;
  transition: background-color 0.3s;
}
#stream-button:hover {
  background-color: #45a049;
}
#stream-button:active {
  background-color: #3e8e41;
  transform: translateY(1px);
}
</style>
