import { useState } from "react";
import "@/App.css";
import axios from "axios";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Download, Video, Loader2, CheckCircle, Youtube } from "lucide-react";
import { toast } from "sonner";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

function App() {
  const [videoUrl, setVideoUrl] = useState("");
  const [videoInfo, setVideoInfo] = useState(null);
  const [selectedFormat, setSelectedFormat] = useState("");
  const [loading, setLoading] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [downloadLink, setDownloadLink] = useState(null);

  const fetchVideoInfo = async () => {
    if (!videoUrl.trim()) {
      toast.error("Please enter a valid YouTube URL");
      return;
    }

    setLoading(true);
    setVideoInfo(null);
    setSelectedFormat("");
    setDownloadLink(null);

    try {
      const response = await axios.post(`${API}/video/info`, { url: videoUrl });
      setVideoInfo(response.data);
      if (response.data.formats.length > 0) {
        setSelectedFormat(response.data.formats[0].format_id);
      }
      toast.success("Video information loaded successfully!");
    } catch (error) {
      console.error("Error fetching video info:", error);
      toast.error(error.response?.data?.detail || "Failed to fetch video information");
    } finally {
      setLoading(false);
    }
  };

  const handleDownload = async () => {
    if (!selectedFormat) {
      toast.error("Please select a video quality");
      return;
    }

    setDownloading(true);
    setDownloadLink(null);

    try {
      const response = await axios.post(`${API}/video/download`, {
        url: videoUrl,
        format_id: selectedFormat
      });
      
      const downloadUrl = `${API}/video/file/${response.data.filename}`;
      setDownloadLink(downloadUrl);
      toast.success("Video ready for download!");
    } catch (error) {
      console.error("Error downloading video:", error);
      toast.error(error.response?.data?.detail || "Failed to download video");
    } finally {
      setDownloading(false);
    }
  };

  const formatFileSize = (bytes) => {
    if (!bytes) return "Unknown size";
    const mb = bytes / (1024 * 1024);
    return `${mb.toFixed(2)} MB`;
  };

  return (
    <div className="App">
      {/* Hero Section */}
      <section className="hero-section">
        <div className="hero-content">
          <div className="hero-icon-wrapper">
            <div className="hero-icon-bg">
              <Video className="hero-icon" size={48} />
            </div>
          </div>
          
          <h1 className="hero-title" data-testid="main-heading">
            Download Videos from Social Media Easily
          </h1>
          
          <p className="hero-subtitle" data-testid="hero-subtitle">
            Fast, free, and simple YouTube video downloader. Choose your preferred quality and download in seconds.
          </p>

          {/* Input Form */}
          <Card className="input-card" data-testid="input-card">
            <CardContent className="input-card-content">
              <div className="input-wrapper">
                <div className="url-input-container">
                  <Youtube className="input-icon" size={20} />
                  <Input
                    data-testid="video-url-input"
                    type="url"
                    placeholder="Paste YouTube video URL here..."
                    value={videoUrl}
                    onChange={(e) => setVideoUrl(e.target.value)}
                    onKeyPress={(e) => e.key === 'Enter' && fetchVideoInfo()}
                    className="video-input"
                  />
                </div>
                <Button
                  data-testid="fetch-info-button"
                  onClick={fetchVideoInfo}
                  disabled={loading}
                  className="fetch-button"
                >
                  {loading ? (
                    <>
                      <Loader2 className="animate-spin" size={20} />
                      <span>Loading...</span>
                    </>
                  ) : (
                    <>
                      <Video size={20} />
                      <span>Get Video</span>
                    </>
                  )}
                </Button>
              </div>
            </CardContent>
          </Card>

          {/* Video Info Card */}
          {videoInfo && (
            <Card className="video-info-card" data-testid="video-info-card">
              <CardHeader>
                <div className="video-info-header">
                  <img
                    src={videoInfo.thumbnail}
                    alt={videoInfo.title}
                    className="video-thumbnail"
                    data-testid="video-thumbnail"
                  />
                  <div className="video-details">
                    <CardTitle className="video-title" data-testid="video-title">
                      {videoInfo.title}
                    </CardTitle>
                    <CardDescription data-testid="video-duration">
                      Duration: {Math.floor(videoInfo.duration / 60)}:{(videoInfo.duration % 60).toString().padStart(2, '0')}
                    </CardDescription>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="video-info-content">
                <div className="format-selection">
                  <label className="format-label" data-testid="quality-label">
                    Select Quality:
                  </label>
                  <Select value={selectedFormat} onValueChange={setSelectedFormat}>
                    <SelectTrigger className="format-select" data-testid="quality-select">
                      <SelectValue placeholder="Choose quality" />
                    </SelectTrigger>
                    <SelectContent>
                      {videoInfo.formats.map((format) => (
                        <SelectItem
                          key={format.format_id}
                          value={format.format_id}
                          data-testid={`quality-option-${format.format_id}`}
                        >
                          {format.resolution} - {format.ext.toUpperCase()}
                          {format.filesize && ` (${formatFileSize(format.filesize)})`}
                          {format.format_note && ` - ${format.format_note}`}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <Button
                  data-testid="download-button"
                  onClick={handleDownload}
                  disabled={downloading || !selectedFormat}
                  className="download-button"
                >
                  {downloading ? (
                    <>
                      <Loader2 className="animate-spin" size={20} />
                      <span>Downloading...</span>
                    </>
                  ) : (
                    <>
                      <Download size={20} />
                      <span>Download Video</span>
                    </>
                  )}
                </Button>

                {downloadLink && (
                  <div className="download-success" data-testid="download-success">
                    <CheckCircle className="success-icon" size={24} />
                    <div className="success-content">
                      <p className="success-text">Your video is ready!</p>
                      <a
                        href={downloadLink}
                        download
                        className="download-link"
                        data-testid="download-link"
                      >
                        Click here to download
                      </a>
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          )}
        </div>
      </section>

      {/* Footer */}
      <footer className="footer" data-testid="footer">
        <p className="footer-text">
          © 2025 VidSaver. All rights reserved.
        </p>
      </footer>
    </div>
  );
}

export default App;
