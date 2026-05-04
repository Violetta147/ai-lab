import onnx
import onnxruntime as ort
import numpy as np

ONNX_MODEL_PATH = "deepstream/best_deepstream_nvidia_output.onnx"
# ONNX_MODEL_PATH = r"D:\datas\Final.yolov8\models\v8n_ModelOpt_Physical_Pruning_KD\weights\best.onnx"
def check_normalization_and_inference(model_path):
    print(f"--- Inspecting: {model_path} ---")
    
    # 1. Check ONNX graph for internal normalization (Div/Mul right after input)
    model = onnx.load(model_path)
    first_input = model.graph.input[0].name
    
    has_internal_norm = any(
        node.op_type in ["Div", "Mul"] and first_input in node.input 
        for node in model.graph.node[:10]
    )
    
    print(f"Internal normalization (1/255) found in graph: {has_internal_norm}")

    # 2. Test output scales with ONNX Runtime to confirm
    session = ort.InferenceSession(model_path, providers=['CPUExecutionProvider'])
    input_name = session.get_inputs()[0].name
    
    # Resolve dynamic batch sizes to 1
    shape = [1 if (isinstance(x, str) or x is None) else x for x in session.get_inputs()[0].shape]
    
    # Dummy tensors
    raw_input = np.full(shape, 150.0, dtype=np.float32)            # [0-255] format
    norm_input = np.full(shape, 150.0 / 255.0, dtype=np.float32)   # [0-1] format
    
    out_raw = session.run(None, {input_name: raw_input})[0]
    out_norm = session.run(None, {input_name: norm_input})[0]
    
    print("\n--- Output Tensors Max Values ---")
    print(f"Raw Input [0-255]   -> Max Value: {np.max(out_raw):.4f}")
    print(f"Norm Input [0-1]    -> Max Value: {np.max(out_norm):.4f}")
    
    if np.max(out_raw) > 1000:
        print("\nConclusion: The raw [0-255] input blew up the tensor values.")
        print("You MUST normalize your images (image / 255.0) before feeding them into this ONNX model.")

if __name__ == "__main__":
    check_normalization_and_inference(ONNX_MODEL_PATH)
