from minio import Minio
from minio.commonconfig import CopySource
from minio.error import S3Error
from ..config import MINIO_URL, MINIO_ACCESS_KEY, MINIO_SECRET_KEY, MINIO_SECURE


class MinioHandler:
    def __init__(self):
        self.client = Minio(
            MINIO_URL,
            access_key=MINIO_ACCESS_KEY,
            secret_key=MINIO_SECRET_KEY,
            secure=MINIO_SECURE,
        )

    def list_objects(self, bucket: str) -> list:
        """Liệt kê tất cả object trong bucket. Trả về danh sách tên."""
        try:
            return [
                obj.object_name
                for obj in self.client.list_objects(bucket, recursive=True)
            ]
        except S3Error as e:
            print(f"⚠️ [MinIO] Error listing objects in '{bucket}': {e}")
            return []

    def download_file_as_str(self, bucket_name: str, object_name: str) -> str:
        """Tải file và trả về nội dung dạng string."""
        response = None
        try:
            response = self.client.get_object(bucket_name, object_name)
            content = response.read().decode('utf-8')
            return content
        except Exception as e:
            print(f"❌ [MinIO] Download as string failed for '{object_name}': {e}")
            return ""
        finally:
            if response is not None:
                response.close()
                response.release_conn()

    def exists(self, bucket: str, name: str) -> bool:
        """Kiểm tra object có tồn tại trong bucket không."""
        try:
            self.client.stat_object(bucket, name)
            return True
        except S3Error:
            return False

    def download_file(self, bucket: str, object_name: str, local_path: str):
        """Tải file từ MinIO về đường dẫn local."""
        self.client.fget_object(bucket, object_name, local_path)

    def upload_file(self, bucket: str, object_name: str, data, length: int = None):
        """Upload file lên MinIO.
        
        Args:
            bucket: Tên bucket.
            object_name: Tên object trên MinIO.
            data: File-like object (BytesIO) hoặc đường dẫn local (str).
            length: Kích thước file (bắt buộc nếu data là file-like object).
        """
        if hasattr(data, 'read'):
            # File-like object (BytesIO, etc.)
            if length is None:
                raise ValueError("'length' is required when uploading file-like objects")
            self.client.put_object(bucket, object_name, data, length=length)
        else:
            # Local file path
            self.client.fput_object(bucket, object_name, data)

    def move_object(self, src_bucket: str, src_name: str,
                    dest_bucket: str, dest_name: str = None):
        """Di chuyển object từ bucket này sang bucket khác (copy + delete)."""
        if dest_name is None:
            dest_name = src_name

        self.ensure_bucket(dest_bucket)

        src = CopySource(src_bucket, src_name)
        self.client.copy_object(dest_bucket, dest_name, src)
        self.client.remove_object(src_bucket, src_name)

    def ensure_bucket(self, bucket_name: str):
        """Tạo bucket nếu chưa tồn tại."""
        if not self.client.bucket_exists(bucket_name):
            self.client.make_bucket(bucket_name)
            print(f"📦 [MinIO] Created bucket: {bucket_name}")
