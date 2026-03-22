from flask import Flask, request, render_template, send_from_directory, jsonify, send_file
from PIL import Image, ImageDraw
import cv2
import numpy as np
import io
import os
import time
import barcode
from barcode.writer import ImageWriter
from pyzbar.pyzbar import decode
import math
import sqlite3
import io
import json
import csv
from flask import make_response, request

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # Limit uploads to 5MB

# Initialize SQLite database
def init_db():
    conn = sqlite3.connect('reviews.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS reviews (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        rating INTEGER NOT NULL,
        comment TEXT NOT NULL,
        timestamp REAL NOT NULL
    )''')
    conn.commit()
    conn.close()

# Call init_db when the app starts
with app.app_context():
    init_db()

@app.route('/')
def landing():
    return send_from_directory('static', 'landing.html')

@app.route('/customize_omr')
def customize_omr():
    return send_from_directory('static', 'customize_omr.html')

@app.route('/grade_omr')
def grade_omr_page():
    return send_from_directory('static', 'grade_omr.html')

@app.route('/generate_omr', methods=['POST'])
def generate_omr():
    try:
        questions = int(request.form.get('numQuestions', 10))
        options = int(request.form.get('numOptions', 4))
        bubble_size = request.form.get('bubbleSize', 'medium')
        bubble_shape = request.form.get('bubbleShape', 'circle')
        student_id = request.form.get('studentId', '')

        # Validate inputs (except student_id)
        if questions < 5 or questions > 50 or options < 2 or options > 6:
            return jsonify({'error': 'Invalid input: Questions (5-50), Options (2-6)'}), 400
        if bubble_size not in ['small', 'medium', 'large']:
            return jsonify({'error': 'Invalid bubble size: small, medium, large'}), 400
        if bubble_shape not in ['circle', 'square']:
            return jsonify({'error': 'Invalid bubble shape: circle, square'}), 400

        # Image parameters
        bubble_sizes = {'small': 8, 'medium': 10, 'large': 12}
        bubble_radius = bubble_sizes[bubble_size]
        spacing = 40
        margin = 50
        id_box_height = 80
        id_spacing = 20
        questions_per_column = 15
        column_spacing = 30

        # Calculate number of columns
        num_columns = math.ceil(questions / questions_per_column)
        
        # Calculate image dimensions
        column_width = options * spacing
        width = margin * 2 + (num_columns * column_width) + (num_columns - 1) * column_spacing
        height = margin * 2 + questions_per_column * spacing + id_box_height + id_spacing

        # Create image
        img = Image.new('RGB', (width, height), 'white')
        draw = ImageDraw.Draw(img)

        # Draw student ID box (always reserve space, even if empty)
        draw.rectangle([margin, margin, margin + 100, margin + 40], outline='black')
        if student_id:
            draw.text((margin + 5, margin + 5), f"ID: {student_id}", fill='black')
            try:
                barcode_img = barcode.get('code39', student_id, writer=ImageWriter()).render()
                barcode_img = barcode_img.resize((100, 20))
                img.paste(barcode_img, (margin, margin + 40))
            except Exception as e:
                print(f"Barcode generation error for student_id '{student_id}': {str(e)}")

        # Draw grid (blank bubbles) in columns
        for q in range(questions):
            # Determine column and row within column
            col = q // questions_per_column
            row = q % questions_per_column
            
            # Calculate position
            x_base = margin + col * (column_width + column_spacing)
            y = margin + id_box_height + id_spacing + row * spacing

            # Draw question number
            draw.text((x_base - 30, y - 5), f"Q{q+1}", fill='black')

            # Draw bubbles for options
            for o in range(options):
                x = x_base + o * spacing
                if bubble_shape == 'circle':
                    draw.ellipse([x - bubble_radius, y - bubble_radius, 
                                 x + bubble_radius, y + bubble_radius], outline='black')
                else:
                    draw.rectangle([x - bubble_radius, y - bubble_radius, 
                                   x + bubble_radius, y + bubble_radius], outline='black')
                # Draw option labels (A, B, C...) above the first row of each column
                if row == 0:
                    draw.text((x - 5, margin + id_box_height + id_spacing - 30), chr(65 + o), fill='black')

        # Save and serve image
        filename = f'blank_omr_{questions}q_{options}o_{bubble_size}_{bubble_shape}_{student_id or "no_id"}.png'
        img.save(filename)
        return send_file(filename, as_attachment=True, download_name=filename)

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/grade', methods=['POST'])
def grade():
    try:
        print("Form data:", request.form)
        print("Files:", request.files)

        num_sheets = int(request.form.get('numSheets', 1))
        same_key = request.form.get('sameKey', 'yes') == 'yes'
        omr_sheets = request.files.getlist('omrSheet')
        num_questions = int(request.form.get('numQuestions', 0))
        num_options = int(request.form.get('numOptions', 0))
        bubble_size = request.form.get('bubbleSize', 'medium')
        bubble_shape = request.form.get('bubbleShape', 'circle')

        # Validate inputs
        if num_sheets < 1 or num_sheets > 10:
            return render_template('result.html', results_files=[({'roll_number': '', 'score': 0, 'total': 0, 
                                                                'details': ['Invalid number of sheets']}, '')])
        if not omr_sheets or len(omr_sheets) != num_sheets or any(sheet.filename == '' for sheet in omr_sheets):
            return render_template('result.html', results_files=[({'roll_number': '', 'score': 0, 'total': 0, 
                                                                'details': ['Please upload all OMR sheets']}, '')])
        if num_questions < 5 or num_questions > 50 or num_options < 2 or num_options > 6:
            return render_template('result.html', results_files=[({'roll_number': '', 'score': 0, 'total': 0, 
                                                                'details': [f'Invalid input: Questions (5-50), Options (2-6), Got {num_questions}/{num_options}']}, '')])
        if bubble_size not in ['small', 'medium', 'large']:
            return render_template('result.html', results_files=[({'roll_number': '', 'score': 0, 'total': 0, 
                                                                'details': ['Invalid bubble size: small, medium, large']}, '')])
        if bubble_shape not in ['circle', 'square']:
            return render_template('result.html', results_files=[({'roll_number': '', 'score': 0, 'total': 0, 
                                                                'details': ['Invalid bubble shape: circle, square']}, '')])

        # Get answer keys
        answer_keys = []
        if same_key:
            correct_answers = [int(request.form.get(f'answer{i}', 0)) for i in range(1, num_questions + 1)]
            if 0 in correct_answers:
                return render_template('result.html', results_files=[({'roll_number': '', 'score': 0, 'total': 0, 
                                                                    'details': [f'Missing answers: Got {correct_answers}']}, '')])
            answer_keys = [correct_answers] * num_sheets
        else:
            for s in range(1, num_sheets + 1):
                correct_answers = [int(request.form.get(f'answer{s}_{i}', 0)) for i in range(1, num_questions + 1)]
                if 0 in correct_answers:
                    return render_template('result.html', results_files=[({'roll_number': '', 'score': 0, 'total': 0, 
                                                                        'details': [f'Missing answers for sheet {s}: Got {correct_answers}']}, '')])
                answer_keys.append(correct_answers)

        # Process each OMR sheet
        results = []
        processed_files = []
        original_filenames = []  # Store original filenames
        bubble_sizes = {'small': 8, 'medium': 10, 'large': 12}
        bubble_radius = bubble_sizes[bubble_size]
        spacing = 40
        margin = 50
        id_box_height = 80
        id_spacing = 20
        questions_per_column = 15
        column_spacing = 30
        column_width = num_options * spacing
        num_columns = math.ceil(num_questions / questions_per_column)

        for sheet_idx, (omr_sheet, correct_answers) in enumerate(zip(omr_sheets, answer_keys), 1):
            # Store the original filename
            original_filename = omr_sheet.filename
            original_filenames.append(original_filename)

            # Read the file
            image_data = omr_sheet.read()
            if not image_data:
                return render_template('result.html', results_files=[({'roll_number': '', 'score': 0, 'total': 0, 
                                                                    'details': [f'Empty file uploaded for sheet {sheet_idx}']}, '')])

            # Load image directly with OpenCV
            img_np_bgr = cv2.imdecode(np.frombuffer(image_data, np.uint8), cv2.IMREAD_COLOR)
            if img_np_bgr is None:
                return render_template('result.html', results_files=[({'roll_number': '', 'score': 0, 'total': 0, 
                                                                    'details': [f'Failed to load image for sheet {sheet_idx}']}, '')])

            # Convert to grayscale for bubble detection
            img_np = cv2.cvtColor(img_np_bgr, cv2.COLOR_BGR2GRAY)

            # Resize
            max_height = 800
            if img_np.shape[0] > max_height:
                scale = max_height / img_np.shape[0]
                img_np = cv2.resize(img_np, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
                img_np_bgr = cv2.resize(img_np_bgr, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)

            # Threshold
            _, thresh = cv2.threshold(img_np, 180, 255, cv2.THRESH_BINARY_INV)

            # Detect roll number (via barcode, assuming barcode encodes roll number)
            try:
                decoded = decode(img_np_bgr)
                roll_number = decoded[0].data.decode('utf-8') if decoded else f'sheet_{sheet_idx}'
            except Exception as e:
                print(f"Barcode detection error for sheet {sheet_idx}: {str(e)}")
                roll_number = f'sheet_{sheet_idx}'

            # Detect bubbles
            detected_answers = []
            for q in range(num_questions):
                col = q // questions_per_column
                row = q % questions_per_column
                x_base = margin + col * (column_width + column_spacing)
                y = int(margin + id_box_height + id_spacing + row * spacing)

                max_filled = 0
                selected_option = 0
                for o in range(num_options):
                    x = int(x_base + o * spacing)
                    if bubble_shape == 'circle':
                        region = thresh[y-bubble_radius:y+bubble_radius, x-bubble_radius:x+bubble_radius]
                        if region.size == 0:
                            continue
                        mask = np.zeros_like(region)
                        cv2.circle(mask, (bubble_radius, bubble_radius), bubble_radius, 255, -1)
                        region = cv2.bitwise_and(region, region, mask=mask)
                        total_pixels = np.sum(mask > 0)
                        if total_pixels == 0:
                            continue
                        filled_pixels = np.sum(region > 200)
                        filled_ratio = filled_pixels / total_pixels
                    else:
                        region = thresh[y-bubble_radius:y+bubble_radius, x-bubble_radius:x+bubble_radius]
                        if region.size == 0:
                            continue
                        filled_ratio = np.sum(region > 200) / region.size
                    if filled_ratio > max_filled:
                        max_filled = filled_ratio
                        selected_option = o + 1
                detected_answers.append(selected_option if max_filled > 0.4 else 0)

            # Grade
            score = 0
            details = []
            for i, (detected, correct) in enumerate(zip(detected_answers, correct_answers), 1):
                if detected == 0:
                    details.append(f"Q{i}: No answer detected")
                elif detected == correct:
                    score += 1
                    details.append(f"Q{i}: Correct (Marked: {chr(64+detected)}, Correct: {chr(64+correct)})")
                else:
                    details.append(f"Q{i}: Incorrect (Marked: {chr(64+detected)}, Correct: {chr(64+correct)})")

            # Create processed image with markings (convert BGR to RGB for PIL)
            img_rgb = cv2.cvtColor(img_np_bgr, cv2.COLOR_BGR2RGB)
            img_pil = Image.fromarray(img_rgb)
            draw = ImageDraw.Draw(img_pil)
            for q, (detected, correct) in enumerate(zip(detected_answers, correct_answers)):
                col = q // questions_per_column
                row = q % questions_per_column
                x_base = margin + col * (column_width + column_spacing)
                y = margin + id_box_height + id_spacing + row * spacing
                for o in range(num_options):
                    x = x_base + o * spacing
                    if o + 1 == detected:
                        color = 'green' if detected == correct else 'red'
                        if bubble_shape == 'circle':
                            draw.ellipse([x - bubble_radius, y - bubble_radius, 
                                         x + bubble_radius, y + bubble_radius], outline=color, width=2)
                        else:
                            draw.rectangle([x - bubble_radius, y - bubble_radius, 
                                           x + bubble_radius, y + bubble_radius], outline=color, width=2)

            # Save processed image with the original filename
            processed_filename = original_filename
            img_pil.save(os.path.join('static', processed_filename))
            processed_files.append(processed_filename)

            # Store result, using original filename as roll_number
            results.append({
                'roll_number': original_filename,  # Use original filename instead of barcode
                'score': score,
                'total': num_questions,
                'details': details
            })

        # Zip results and files together
        results_files = list(zip(results, processed_files))

        return render_template('result.html', results_files=results_files)

    except Exception as e:
        print("Error:", str(e))
        return render_template('result.html', results_files=[({'roll_number': '', 'score': 0, 'total': 0, 
                                                            'details': [f"Error: {str(e)}"]}, '')])

@app.route('/download/<filename>')
def download_file(filename):
    return send_from_directory('static', filename, as_attachment=True, download_name=filename)

@app.route('/reviews', methods=['GET', 'POST'])
def handle_reviews():
    if request.method == 'POST':
        try:
            data = request.get_json()
            rating = int(data.get('rating', 0))
            comment = data.get('comment', '').strip()
            if rating < 1 or rating > 5 or not comment:
                return jsonify({'error': 'Invalid rating or empty comment'}), 400
            
            # Insert review into the database
            conn = sqlite3.connect('reviews.db')
            c = conn.cursor()
            c.execute('INSERT INTO reviews (rating, comment, timestamp) VALUES (?, ?, ?)',
                     (rating, comment, time.time()))
            conn.commit()
            conn.close()
            return jsonify({'success': True})
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    else:
        # Retrieve all reviews from the database
        try:
            conn = sqlite3.connect('reviews.db')
            c = conn.cursor()
            c.execute('SELECT rating, comment, timestamp FROM reviews ORDER BY timestamp DESC')
            reviews = [{'rating': row[0], 'comment': row[1], 'timestamp': row[2]} for row in c.fetchall()]
            conn.close()
            return jsonify(reviews)
        except Exception as e:
            return jsonify({'error': str(e)}), 500

@app.route("/admin/reviews")
def admin_reviews():
    return render_template("admin_reviews.html")

@app.route("/reviews/delete/<float:timestamp>", methods=["DELETE"])
def delete_review(timestamp):
    try:
        conn = sqlite3.connect('reviews.db')
        c = conn.cursor()
        c.execute("DELETE FROM reviews WHERE timestamp = ?", (timestamp,))
        conn.commit()
        conn.close()
        return jsonify({"success": True})
    except Exception as e:
        print("Delete error:", e)
        return jsonify({"error": str(e)}), 500

@app.route('/export_csv', methods=['POST'])
def export_csv():
    try:
        results_json = request.form.get('results')
        if not results_json:
            return "No data to export", 400

        results = json.loads(results_json)

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['Roll Number', 'Score', 'Total', 'Details'])

        for result in results:
            writer.writerow([
                result['roll_number'],
                result['score'],
                result['total'],
                '; '.join(result['details'])
            ])

        response = make_response(output.getvalue())
        response.headers['Content-Disposition'] = 'attachment; filename=grading_results.csv'
        response.headers['Content-Type'] = 'text/csv'
        return response

    except Exception as e:
        print("CSV Export Error:", str(e))
        return "Error exporting CSV", 500

if __name__ == '__main__':
    os.makedirs('static', exist_ok=True)
    os.makedirs('templates', exist_ok=True)
    app.run(debug=True)


