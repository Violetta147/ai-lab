pipeline ta định xây là sau khi quyết định thuật toán thì ta sẽ biết được cần vẽ đa giác (polygon) hay là vẽ mấy cái vạch từ đó ta sẽ dùng script setup deepstream phù hợp
sau đó ta sẽ bỏ models,file labels.txt (chứa các class mà model sẽ inference), file onnx và script setupdeepstream lên jetson nano, ta sẽ cấu hình cho nó chạy 

phía server ta sẽ chọn y thuật toán đó ở mục deep analysis, chọn thuật toán đó thì nó sẽ hiện các thông số tương ứng rồi ta bắt đầu bật các luồng camera lên,ffmpeg nó sẽ truyền (đẩy) tới mediamtx
, jetson sẽ bắt dầu kéo frame từ mediamtx về chạy inference -> tracking trong cái đa giác, hoặc xe đi qua cái vạch đó hoặc đi ra khỏi cái vạch đó rồi gửi mấy "dữ liệu ni" về server

trước đó server cũng kéo frame cùng lúc (dường như là vậy) với jetson về rồi đợi nhận "dữ liệu ni" nữa rồi ghép vô (cùng tracking_id, cùng source_id (luồng camera)) rồi bỏ vô thuật toán mật độ
tính rồi đưa lên web bằng websocket
