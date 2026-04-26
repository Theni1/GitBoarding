import type { FileResult } from "@/lib/api";
import FilePath from "./FilePath";

export default function OnboardingPath({ files }: { files: FileResult[] }) {
  return (
    <div className="space-y-2">
      {files.map((file) => (
        <FilePath key={file.path} file={file} isTop={file.rank === 1} />
      ))}
    </div>
  );
}
