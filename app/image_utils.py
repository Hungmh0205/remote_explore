import os
from concurrent.futures import ProcessPoolExecutor
import multiprocessing

# Global executor
process_pool: ProcessPoolExecutor = None

def init_pool():
    global process_pool
    # Limit to exactly 2 workers to save RAM as requested
    process_pool = ProcessPoolExecutor(max_workers=2)

def shutdown_pool():
    global process_pool
    if process_pool:
        process_pool.shutdown(wait=True)

def cpu_bound_generate_thumb(input_path: str, output_path: str) -> bool:
    """
    Standalone function to be pickled and run in a separate process.
    Returns True if successful, False otherwise.
    """
    try:
        from PIL import Image
        
        # Ensure output dir exists (safety check, though API does it)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        with Image.open(input_path) as img:
            # Check dimensions again to be safe
            if img.width <= 200 and img.height <= 200:
                # If small enough, maybe just copy or save directly?
                # But to keep consistent format (JPEG), let's save.
                pass
            
            img.thumbnail((200, 200))
            
            # Convert mode to RGB if necessary for JPEG
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
                
            # Save to temporary file first to avoid partial writes on crash
            tmp_out = output_path + ".tmp"
            img.save(tmp_out, "JPEG", quality=80)
            
            # Atomic rename
            os.replace(tmp_out, output_path)
            return True
    except Exception:
        return False
