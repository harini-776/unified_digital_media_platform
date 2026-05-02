import { VideoUploader } from "@/components/video/VideoUploader";

export default function UploadPage() {
  return (
    <div className="min-h-[calc(100vh-4rem)] flex items-center justify-center px-4">
      <div className="w-full max-w-2xl space-y-8">
        <div className="text-center space-y-2">
          <h1 className="text-3xl font-bold">Analyze a Video</h1>
          <p className="text-muted-foreground">
            Upload a video file to check for deepfake manipulation and verify its provenance.
          </p>
        </div>
        <VideoUploader />
        <div className="text-center text-sm text-muted-foreground space-y-1">
          <p>Supported formats: MP4, MOV, AVI, WebM, MKV (max 500MB)</p>
          <p>Videos are processed securely and never shared.</p>
        </div>
      </div>
    </div>
  );
}
