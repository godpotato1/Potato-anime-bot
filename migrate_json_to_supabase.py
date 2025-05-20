# migrate_json_to_supabase.py
import json
from datetime import datetime
from config import logger
from storage import add_episode

JSON_PATH = 'episodes.json'


def migrate():
    """
    خواندن episodes.json (که یک دیکشنری code: message_id هست)
    و درج رکوردها در Supabase
    """
    try:
        with open(JSON_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        logger.error(f"Error reading JSON file: {e}", exc_info=True)
        return

    for code, message_id in data.items():
        # استخراج quality از انتهای کد (مثلاً '720' از '..._720')
        try:
            quality = int(code.split('_')[-1])
        except ValueError:
            quality = 0
        episode = {
            'code': code,
            'message_id': message_id,
            'date_added': datetime.now().isoformat(),
            'title': code,
            'quality': quality
        }
        success = add_episode(episode)
        if success:
            logger.info(f"Inserted episode {code}")
        else:
            logger.warning(f"Failed to insert episode {code}")

if __name__ == '__main__':
    migrate()
