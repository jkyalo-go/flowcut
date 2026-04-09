import asyncio
import time
from pathlib import Path
from sqlalchemy.orm import Session
from database import SessionLocal
from models import Clip, SubClip, TimelineItem, ProcessingStatus, ClipType
from services.transcriber import extract_audio, transcribe_file
from services.classifier import classify
from services.silence_remover import get_duration
from routes.ws import broadcast
from config import BROLL_NUM_CLIPS, BROLL_CLIP_DURATION


async def process_clip(clip_id: int):
    db: Session = SessionLocal()
    try:
        clip = db.query(Clip).filter(Clip.id == clip_id).first()
        if not clip:
            return

        project_id = clip.project_id

        # Get duration
        try:
            clip.duration = await get_duration(clip.source_path)
        except Exception:
            clip.duration = 0

        total_duration = clip.duration or 0

        # --- Step 1: Transcribe (0-70% of overall) ---
        clip.status = ProcessingStatus.TRANSCRIBING
        db.commit()
        await broadcast(project_id, "clip_progress", {
            "clip_id": clip_id, "status": "transcribing",
            "progress": 0, "detail": "extracting audio",
        })

        audio_path = await extract_audio(clip.source_path)

        await broadcast(project_id, "clip_progress", {
            "clip_id": clip_id, "status": "transcribing",
            "progress": 20, "detail": "sending to Deepgram",
        })

        try:
            text, segments = await asyncio.to_thread(transcribe_file, audio_path)
        finally:
            import os
            os.unlink(audio_path)
        clip.transcript = text

        # Debug: print transcript with timestamps
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"=== TRANSCRIPT for clip {clip_id} ({len(segments)} segments) ===")
        for seg in segments:
            logger.info(f"  [{seg['start']:.2f}s -> {seg['end']:.2f}s] ({seg['end']-seg['start']:.2f}s) {seg['text']}")
        logger.info(f"=== END TRANSCRIPT ===")

        # --- Step 2: Classify (instant, 70-72%) ---
        clip.status = ProcessingStatus.CLASSIFYING
        db.commit()
        await broadcast(project_id, "clip_progress", {
            "clip_id": clip_id, "status": "classifying",
            "progress": 72, "detail": "classifying clip type",
        })

        clip_type = classify(text)
        clip.clip_type = clip_type

        # --- Step 3: Analyze & store time ranges (72-100%) ---
        clip.status = ProcessingStatus.PROCESSING
        db.commit()

        if clip_type == ClipType.TALKING:
            await broadcast(project_id, "clip_progress", {
                "clip_id": clip_id, "status": "processing",
                "progress": 80, "detail": "building speech segments from transcript",
            })

            # Use transcript segment timestamps directly as speech regions
            speech_segments = [
                (seg["start"], seg["end"])
                for seg in segments
                if (seg["end"] - seg["start"]) >= 0.1
            ]

            # Store each speech segment as a SubClip
            for i, (start, end) in enumerate(speech_segments):
                sub = SubClip(
                    clip_id=clip_id,
                    start_time=start,
                    end_time=end,
                    label=f"speech {i + 1}",
                )
                db.add(sub)

            clip.status = ProcessingStatus.DONE
            db.commit()

            # Add all speech segments to timeline
            max_pos = db.query(TimelineItem.position).filter(
                TimelineItem.project_id == project_id
            ).order_by(TimelineItem.position.desc()).first()
            next_pos = (max_pos[0] + 1) if max_pos else 0

            for sub in clip.sub_clips:
                item = TimelineItem(
                    project_id=project_id,
                    sub_clip_id=sub.id,
                    position=next_pos,
                )
                db.add(item)
                next_pos += 1

            db.commit()

            await broadcast(project_id, "clip_done", {
                "clip_id": clip_id,
                "clip_type": "talking",
            })

        else:
            await broadcast(project_id, "clip_progress", {
                "clip_id": clip_id, "status": "processing",
                "progress": 80, "detail": "picking b-roll moments",
            })

            # Evenly space clips, avoiding first/last 2 seconds
            margin = 2.0 if total_duration > (BROLL_CLIP_DURATION + 4) else 0
            usable_start = margin
            usable_end = total_duration - margin
            usable_duration = usable_end - usable_start

            if usable_duration < BROLL_CLIP_DURATION:
                # Clip too short, just use the whole thing
                moments = [{"start": 0, "end": min(BROLL_CLIP_DURATION, total_duration)}]
            else:
                step = usable_duration / (BROLL_NUM_CLIPS + 1)
                moments = []
                for i in range(BROLL_NUM_CLIPS):
                    center = usable_start + step * (i + 1)
                    s = center - BROLL_CLIP_DURATION / 2
                    s = max(usable_start, s)
                    e = s + BROLL_CLIP_DURATION
                    if e > usable_end:
                        e = usable_end
                        s = max(usable_start, e - BROLL_CLIP_DURATION)
                    moments.append({"start": s, "end": e})

            for i, m in enumerate(moments):
                sub = SubClip(
                    clip_id=clip_id,
                    start_time=m["start"],
                    end_time=m["end"],
                    label=f"moment {i + 1}",
                )
                db.add(sub)

            clip.status = ProcessingStatus.DONE
            db.commit()

            # Add b-roll moments to timeline
            max_pos = db.query(TimelineItem.position).filter(
                TimelineItem.project_id == project_id
            ).order_by(TimelineItem.position.desc()).first()
            next_pos = (max_pos[0] + 1) if max_pos else 0

            for sub in clip.sub_clips:
                item = TimelineItem(
                    project_id=project_id,
                    sub_clip_id=sub.id,
                    position=next_pos,
                )
                db.add(item)
                next_pos += 1

            db.commit()

            await broadcast(project_id, "clip_done", {
                "clip_id": clip_id,
                "clip_type": "broll",
            })

        await broadcast(project_id, "clip_progress", {
            "clip_id": clip_id, "status": "done",
            "progress": 100, "detail": "complete",
        })
        await broadcast(project_id, "timeline_updated", {})

    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"\n!!! CLIP {clip_id} FAILED: {e}\n", flush=True)
        clip = db.query(Clip).filter(Clip.id == clip_id).first()
        if clip:
            clip.status = ProcessingStatus.ERROR
            clip.error_message = str(e)[:500]
            db.commit()
        await broadcast(project_id, "clip_error", {"clip_id": clip_id, "error": str(e)[:500]})
        raise
    finally:
        db.close()
