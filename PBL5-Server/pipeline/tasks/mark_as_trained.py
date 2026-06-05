import sys
import os

# Thêm đường dẫn để import được pipeline
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from pipeline.utils.db_handler import DBHandler
from pipeline.utils.telegram_handler import TelegramHandler


def main():
    db = DBHandler()
    tg = TelegramHandler()

    print("🔄 [Training] Starting to mark data as TRAINED...")

    try:
        # 1. Đếm số lượng ảnh LABELED trước khi cập nhật
        count = db.count_by_status('LABELED')

        if count == 0:
            print("ℹ️ [Training] No 'LABELED' records found. Nothing to update.")
            return

        # 2. Cập nhật trạng thái sang TRAINED (dùng DBHandler method)
        updated = db.batch_update_status('LABELED', 'TRAINED')

        print(f"✅ [Training] Successfully marked {updated} records as TRAINED.")

        # 3. Thông báo qua Telegram
        msg = (
            f"🎓 *Training Session Completed*\n\n"
            f"✅ Successfully marked `{updated}` images as *TRAINED*.\n"
            f"🚀 These images are now part of your model's history!"
        )
        tg.send_message(msg)

    except Exception as e:
        print(f"❌ [Training] Error: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
