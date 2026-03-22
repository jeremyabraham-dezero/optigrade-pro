import sys
import random
from PIL import Image, ImageDraw
import math
import barcode
from barcode.writer import ImageWriter

def generate_omr_sheet(num_questions, num_options, bubble_size='medium', bubble_shape='circle', student_id='12345'):
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
    num_columns = math.ceil(num_questions / questions_per_column)
    
    # Calculate image dimensions
    column_width = num_options * spacing
    width = margin * 2 + (num_columns * column_width) + (num_columns - 1) * column_spacing
    height = margin * 2 + questions_per_column * spacing + id_box_height + id_spacing

    # Create image
    img = Image.new('RGB', (width, height), 'white')
    draw = ImageDraw.Draw(img)

    # Draw student ID box
    draw.rectangle([margin, margin, margin + 100, margin + 40], outline='black')
    draw.text((margin + 5, margin + 5), f"ID: {student_id}", fill='black')
    try:
        barcode_img = barcode.get('code39', student_id, writer=ImageWriter()).render()
        barcode_img = barcode_img.resize((100, 20))
        img.paste(barcode_img, (margin, margin + 40))
    except Exception as e:
        print(f"Barcode generation error: {str(e)}")

    # Randomly fill bubbles (95% chance to fill a bubble for each question)
    filled_answers = []
    for q in range(num_questions):
        if random.random() < 0.95:  # 95% chance to fill a bubble
            filled_option = random.randint(1, num_options)  # Randomly select an option (1 to num_options)
        else:
            filled_option = 0  # No bubble filled
        filled_answers.append(filled_option)

        # Determine column and row within column
        col = q // questions_per_column
        row = q % questions_per_column
        
        # Calculate position
        x_base = margin + col * (column_width + column_spacing)
        y = margin + id_box_height + id_spacing + row * spacing

        # Draw question number
        draw.text((x_base - 30, y - 5), f"Q{q+1}", fill='black')

        # Draw bubbles for options
        for o in range(num_options):
            x = x_base + o * spacing
            if bubble_shape == 'circle':
                if filled_option == o + 1:
                    draw.ellipse([x - bubble_radius, y - bubble_radius, 
                                 x + bubble_radius, y + bubble_radius], outline='black', fill='black')
                else:
                    draw.ellipse([x - bubble_radius, y - bubble_radius, 
                                 x + bubble_radius, y + bubble_radius], outline='black')
            else:
                if filled_option == o + 1:
                    draw.rectangle([x - bubble_radius, y - bubble_radius, 
                                   x + bubble_radius, y + bubble_radius], outline='black', fill='black')
                else:
                    draw.rectangle([x - bubble_radius, y - bubble_radius, 
                                   x + bubble_radius, y + bubble_radius], outline='black')
            # Draw option labels (A, B, C...) above the first row of each column
            if row == 0:
                draw.text((x - 5, margin + id_box_height + id_spacing - 30), chr(65 + o), fill='black')

    # Save image
    filename = f'filled_omr_{num_questions}q_{num_options}o_{bubble_size}_{bubble_shape}_{student_id}.png'
    img.save(filename)
    print(f"OMR sheet generated: {filename}")
    print(f"Filled answers: {filled_answers}")  # 0 means no bubble, 1=A, 2=B, etc.

if __name__ == "__main__":
    # Default values
    default_questions = 30
    default_options = 4

    # Parse command-line arguments
    try:
        if len(sys.argv) == 3:
            num_questions = int(sys.argv[1])
            num_options = int(sys.argv[2])
        else:
            num_questions = default_questions
            num_options = default_options
            print(f"No arguments provided. Using defaults: {num_questions} questions, {num_options} options")

        # Validate inputs
        if num_questions < 5 or num_questions > 50:
            print("Error: Number of questions must be between 5 and 50")
            sys.exit(1)
        if num_options < 2 or num_options > 6:
            print("Error: Number of options must be between 2 and 6")
            sys.exit(1)

        # Generate the OMR sheet
        generate_omr_sheet(num_questions, num_options)

    except ValueError:
        print("Error: Please provide valid integer arguments for number of questions and options")
        print("Example: python generate_omr.py 15 4")
        sys.exit(1)