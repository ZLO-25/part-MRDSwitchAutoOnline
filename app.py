import os
import subprocess
from flask import Flask, render_template, request, jsonify, flash

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # 請自行設定一個秘密字串

# 全域變數，用來保存執行結果的 log 與 simulation output
log_output_global = ""
simulation_output = ""

# 上傳檔案將覆蓋到此路徑 (位於 src/ 目錄下)
LOCAL_YML_PATH = os.path.join(os.getcwd(), 'src', 'target_switch.yml')

@app.route('/', methods=['GET', 'POST'])
def index():
    global log_output_global, simulation_output
    # 每次處理 POST 前先清空 simulation output
    simulation_output = ""
    if request.method == 'POST':
        # 取得使用者選擇的 Python 檔案（radio button）
        python_file = request.form.get('python_file')
        # 取得上傳的 target_switch.yml 檔案
        uploaded_file = request.files.get('target_switch')
        
        if not python_file:
            flash("請選擇要執行的 Python 檔案")
        elif not uploaded_file:
            flash("請上傳 target_switch.yml")
        else:
            # 儲存上傳的 YAML 檔案到 src/target_switch.yml，覆蓋原有檔案
            try:
                uploaded_file.save(LOCAL_YML_PATH)
            except Exception as ex:
                flash("儲存檔案失敗：" + str(ex))
            
            # 構建命令：假設所有 Python 檔案都位於 src/ 目錄下
            command = ['python3', python_file]
            
            # 設定 cwd 為 src 資料夾的絕對路徑
            app_dir = os.path.dirname(os.path.abspath(__file__))
            src_dir = os.path.join(app_dir, 'src')
            
            try:
                result = subprocess.run(
                    command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=True,
                    cwd=src_dir
                )
                log_output_global = result.stdout + "\n" + result.stderr
            except subprocess.CalledProcessError as e:
                log_output_global = e.stdout + "\n" + e.stderr

            # 根據不同的 Python 檔案讀取對應的 simulation output 檔案
            if python_file == "check_status.py":
                output_path = os.path.join(src_dir, "check_output", "simulation_status_check_output", "simulation_result.txt")
                try:
                    with open(output_path, "r", encoding="utf-8") as f:
                        simulation_output = f.read()
                except Exception as e:
                    simulation_output = "讀取 simulation output 錯誤：" + str(e)
            elif python_file == "check_lldp.py":
                output_path = os.path.join(src_dir, "check_output", "simulation_lldp_check", "simulation_result.txt")
                try:
                    with open(output_path, "r", encoding="utf-8") as f:
                        simulation_output = f.read()
                except Exception as e:
                    simulation_output = "讀取 simulation output 錯誤：" + str(e)
            # 若選擇 update_config.py，則不讀取 simulation output，保持空字串

    return render_template('index.html', log_output=log_output_global, simulation_output=simulation_output)

@app.route('/clear_logs', methods=['POST'])
def clear_logs():
    global log_output_global
    log_output_global = ""
    return jsonify({"status": "success", "message": "Log cleared"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
