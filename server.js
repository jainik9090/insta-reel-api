
const express = require("express");
const cors = require("cors");
const axios = require("axios");

const app = express();

app.use(cors());
app.use(express.json()); 

app.get("/", (req, res) => {
  res.send("Server is running...");
});

app.post("/download-reel", async (req, res) => {
  try {
    const { url } = req.body;
    if (!url || typeof url !== "string") {
      return res.status(400).json({ error: "Invalid or missing 'url'" });
    }
    console.log("Forwarding reel URL to backend:", url);

    const backendUrl = "http://13.60.14.173:8053/download-reel";
    const response = await axios.post(
      backendUrl,
      { url }, 
      { headers: { "Content-Type": "application/json" } }
    );
    res.status(response.status).json(response.data);
  } catch (err) {
    console.error("Proxy error:", err.message);
    if (err.response) {
      return res
        .status(err.response.status)
        .json(err.response.data || { error: "Upstream server error" });
    }
    res.status(500).json({ error: "Proxy failed", detail: err.message });
  }
});

const PORT = process.env.PORT || 3001;
app.listen(PORT, "0.0.0.0", () => {
  console.log(`Server running on port ${PORT}`);
});
