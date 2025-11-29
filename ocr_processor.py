import cv2
import pytesseract
from PIL import Image
from ultralytics import YOLO
import os
import time
import pandas as pd
import arabic_reshaper
from bidi.algorithm import get_display
import re
import shutil
from datetime import datetime
import sys


pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

YOLO_WEIGHTS_PATH = 'egyId_weights.pt'
IDS_CSV_PATH = 'ids.csv'

YOLO_OUTPUT_DIR = r'runs\detect\predict'


def arabic_to_english(text):
    if text is None:
        return None

    arabic_numbers = {
        "٠": "0", "١": "1", "٢": "2", "٣": "3", "٤": "4",
        "٥": "5", "٦": "6", "٧": "7", "٨": "8", "٩": "9"
    }

    english_text = ""
    for ch in text:
        english_text += arabic_numbers.get(ch, ch)

    return english_text


def resize(image, flag):
    if flag == "id":
        return cv2.resize(image, (650, 800))
    elif flag == 1:
        return cv2.resize(image, (780, 540), interpolation=cv2.INTER_LINEAR)
    elif flag == "firstname":
        return cv2.resize(image, (600, 200))
    elif flag == "secondname":
        return cv2.resize(image, (500, 200))
    else:
        return image


def invert(image):
    return cv2.bitwise_not(image)


def gray(image):
    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)


def threshold(image):
    im_bw, th = cv2.threshold(image, 160, 195, cv2.THRESH_BINARY)
    return th


def processing(image, flag):
    resized_image = resize(image, flag)
    inverted_image = invert(resized_image)
    gray_image = gray(inverted_image)
    threshold_image = threshold(gray_image)
    return threshold_image


def run_ocr_on_file(uploaded_file_path):
    image_names = ['firstname', "national_id", "second name", "manfucturing_id"]

    predict_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), YOLO_OUTPUT_DIR)
    if os.path.exists(predict_dir):
        shutil.rmtree(predict_dir)

    try:
        model = YOLO(YOLO_WEIGHTS_PATH)
        results = model(uploaded_file_path, save=True, conf=0.6, imgsz=640, show=False, save_crop=True,
                        project='runs/detect', name='predict')


        output_folder_base = os.path.join('runs', 'detect', 'predict')
        crops_folder = os.path.join(output_folder_base, 'crops')

    except Exception as e:
        raise Exception(f"YOLO Model Error: {e}. Check {YOLO_WEIGHTS_PATH} and model dependencies.")


    images_dict = {}
    file_name_no_ext = os.path.splitext(os.path.basename(uploaded_file_path))[0]

    for name in image_names:
        try:

            img_file = os.path.join(crops_folder, name, f'{file_name_no_ext}.jpg')


            original_filename = os.path.basename(uploaded_file_path)
            img_file_full_name = os.path.join(crops_folder, name, original_filename)

            if os.path.exists(img_file_full_name):
                image = cv2.imread(img_file_full_name)
            elif os.path.exists(img_file):
                image = cv2.imread(img_file)
            else:
                raise FileNotFoundError(f"Cropped image not found for class: {name}")

            images_dict[name] = image

        except Exception as e:
            raise Exception(f"Error loading cropped image for {name}: {e}")


    threshold_firstname = processing(images_dict['firstname'], "firstname")
    threshold_secondname = processing(images_dict['second name'], "secondname")

    firstname = pytesseract.image_to_string(threshold_firstname, lang='ara').strip()
    secondname = pytesseract.image_to_string(threshold_secondname, lang='ara').strip()

    threshold_id = processing(images_dict['national_id'], "id")
    national_id_list = pytesseract.image_to_string(threshold_id, lang="ara_number_id").split()
    national_id = national_id_list[0] if national_id_list else ""


    if not national_id or len(national_id) != 14:
        raise ValueError("National ID extraction failed or ID length is incorrect.")

    english_id = arabic_to_english(national_id)

    try:
        df = pd.read_csv(IDS_CSV_PATH)
        century = english_id[0]
        year_born = english_id[1:3]
        month = english_id[3:5]
        day = english_id[5:7]
        temp_born = english_id[7:9]
        gender_digit = english_id[12]

        place_of_birth_map = {
            '01': "Cairo", '02': "Alexandria", '03': "Port Said", '04': "Suez", '11': "Damietta",
            '12': "Dakahlya", '13': "El Sharkya", '14': "El Kalyobia", '15': "Kafr Elsheikh", '16': "El Gharbia",
            '17': 'El Menofya', '18': "El Behira", '19': "El Esmaalyaa", '21': "Giza", '22': "Beni Suef",
            '23': "Fayium", '24': "El Menya", '25': "Assiut", '26': "Sohag", '27': "Qena",
            '28': "Aswan", '29': "Luxor", '31': "Red Sea", '32': "Wadi El-Gadid", '33': "Matrouh",
            '34': "North Sinai", '35': "South Sinai", '88': "Outside Egypt"
        }

        place_of_birth = place_of_birth_map.get(temp_born, "Unknown")

        current_year = datetime.now().year
        century_prefix = 20 if century == "3" else 19
        birth_year = int(f"{century_prefix}{year_born}")
        age = current_year - birth_year

        gender = "Male" if int(gender_digit) % 2 != 0 else "Female"

    except Exception as e:
        raise Exception(f"Error during ID data analysis: {e}")

    arabic_fname = get_display(arabic_reshaper.reshape(firstname))
    arabic_sname = get_display(arabic_reshaper.reshape(secondname))
    full_name = f"{arabic_fname} {arabic_sname}"

    return {
        "name": full_name.strip(),
        "age": age,
        "gender": gender,
        "address": place_of_birth,
        "national_id": english_id
    }

