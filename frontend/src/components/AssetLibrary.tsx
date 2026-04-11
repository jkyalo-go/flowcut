import { useEffect, useRef, useState } from "react";
import { useTimelineStore } from "../stores/timelineStore";
import type { Asset } from "../types";

export function AssetLibrary() {
  const assets = useTimelineStore((s) => s.assets);
  const setAssets = useTimelineStore((s) => s.setAssets);
  const [collapsed, setCollapsed] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [playingId, setPlayingId] = useState<number | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    fetchAssets();
  }, []);

  const fetchAssets = async () => {
    const res = await fetch("/api/assets?type=music");
    if (res.ok) {
      const data: Asset[] = await res.json();
      setAssets(data);
    }
  };

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;
    setUploading(true);
    for (const file of Array.from(files)) {
      const form = new FormData();
      form.append("file", file);
      await fetch("/api/assets/upload?asset_type=music", {
        method: "POST",
        body: form,
      });
    }
    await fetchAssets();
    setUploading(false);
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const handleDelete = async (id: number) => {
    await fetch(`/api/assets/${id}`, { method: "DELETE" });
    if (playingId === id) {
      audioRef.current?.pause();
      setPlayingId(null);
    }
    await fetchAssets();
  };

  const togglePlay = (asset: Asset) => {
    if (playingId === asset.id) {
      audioRef.current?.pause();
      setPlayingId(null);
      return;
    }
    if (audioRef.current) {
      audioRef.current.pause();
    }
    const audio = new Audio(`/api/assets/${asset.id}/file`);
    audio.onended = () => setPlayingId(null);
    audio.play();
    audioRef.current = audio;
    setPlayingId(asset.id);
  };

  const formatDuration = (s: number) => {
    const m = Math.floor(s / 60);
    const sec = Math.floor(s % 60);
    return `${m}:${sec.toString().padStart(2, "0")}`;
  };

  return (
    <div className="asset-library">
      <div
        className="asset-library-header"
        onClick={() => setCollapsed(!collapsed)}
      >
        <h3>
          <span className={`collapse-arrow ${collapsed ? "collapsed" : ""}`}>
            &#9662;
          </span>
          Music Library
        </h3>
        <span className="asset-count">{assets.length}</span>
      </div>
      {!collapsed && (
        <div className="asset-library-body">
          <label className="btn btn-sm upload-btn">
            {uploading ? "Uploading..." : "Upload Music"}
            <input
              ref={fileInputRef}
              type="file"
              accept=".mp3,.wav,.m4a,.aac,.ogg"
              multiple
              onChange={handleUpload}
              disabled={uploading}
              hidden
            />
          </label>
          {assets.length === 0 ? (
            <p className="asset-empty">No music uploaded yet.</p>
          ) : (
            <ul className="asset-list">
              {assets.map((asset) => (
                <li key={asset.id} className="asset-item">
                  <button
                    className="asset-play-btn"
                    onClick={() => togglePlay(asset)}
                    title={playingId === asset.id ? "Pause" : "Play"}
                  >
                    {playingId === asset.id ? "\u23F8" : "\u25B6"}
                  </button>
                  <span className="asset-name" title={asset.name}>
                    {asset.name}
                  </span>
                  <span className="asset-duration">
                    {formatDuration(asset.duration)}
                  </span>
                  <button
                    className="asset-delete-btn"
                    onClick={() => handleDelete(asset.id)}
                    title="Delete"
                  >
                    &times;
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
