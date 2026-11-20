// Photos for the composer (PLAN §3.17): up to two, JPEG / PNG / WebP, resized in the browser before upload.
// A bad file gets a clear message instead of a silent drop (Q19).
import { X } from "lucide-react";
import { useEffect, useMemo } from "react";

export const MAX_PHOTOS = 2;
const ACCEPT = ["image/jpeg", "image/png", "image/webp"];
export const ACCEPT_ATTR = ACCEPT.join(",");
const MAX_SIDE = 1568;
const MAX_BYTES = 12 * 1024 * 1024;

/** Sorts dropped or picked files into usable photos and the reasons the rest were left out. */
export function checkPhotos(files: File[], already: number): { ok: File[]; errors: string[] } {
  const ok: File[] = [];
  const errors: string[] = [];
  for (const file of files) {
    if (!ACCEPT.includes(file.type)) errors.push(`${file.name}: use a JPEG, PNG or WebP photo.`);
    else if (file.size > MAX_BYTES) errors.push(`${file.name}: larger than 12 MB. Use a smaller photo.`);
    else if (already + ok.length >= MAX_PHOTOS) errors.push(`${file.name}: left out. At most ${MAX_PHOTOS} photos per request.`);
    else ok.push(file);
  }
  return { ok, errors };
}

/** Downscales to 1568 px on the long side and re-encodes as JPEG. Falls back to the original file. */
export async function resizePhoto(file: File): Promise<File> {
  try {
    const bitmap = await createImageBitmap(file);
    const scale = Math.min(1, MAX_SIDE / Math.max(bitmap.width, bitmap.height));
    if (scale === 1 && file.type === "image/jpeg") return file;
    const canvas = document.createElement("canvas");
    canvas.width = Math.round(bitmap.width * scale);
    canvas.height = Math.round(bitmap.height * scale);
    canvas.getContext("2d")?.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
    bitmap.close();
    const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, "image/jpeg", 0.88));
    return blob ? new File([blob], file.name.replace(/\.\w+$/, "") + ".jpg", { type: "image/jpeg" }) : file;
  } catch {
    return file;
  }
}

export function PhotoThumbs({ photos, onRemove, disabled }: { photos: File[]; onRemove: (index: number) => void; disabled?: boolean }) {
  const urls = useMemo(() => photos.map((p) => URL.createObjectURL(p)), [photos]);
  useEffect(() => () => urls.forEach((u) => URL.revokeObjectURL(u)), [urls]);
  if (!photos.length) return null;
  return (
    <ul className="flex gap-2" aria-label="Photos in this request">
      {photos.map((photo, i) => (
        <li key={`${photo.name}-${i}`} className="relative">
          <img src={urls[i]} alt={`Photo ${i + 1}: ${photo.name}`} className="size-16 rounded-md border border-border object-cover" />
          <button
            type="button"
            disabled={disabled}
            onClick={() => onRemove(i)}
            aria-label={`Remove photo ${photo.name}`}
            className="absolute -top-1.5 -right-1.5 flex size-5 items-center justify-center rounded-full border border-border bg-surface text-secondary-text shadow-e1 hover:text-foreground"
          >
            <X className="size-3" strokeWidth={2} aria-hidden />
          </button>
        </li>
      ))}
    </ul>
  );
}
