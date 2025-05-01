# Instagram Auto Poster - Instructions

## Setup Guide

1. **Copy Images to Folder**  
   Place all image files into the `Images` folder before running the software.

2. **Create CSV File**  
   Create a `.csv` file with two columns:
   - `filename`: Name of the image file (e.g., `lion.jpg`)
   - `caption`: Instagram caption for the image
   
   > *Note: Do not include a `posted` column. The software will manage that internally.*

3. **Automatic Posting Logic**  
   - The software marks each image as `posted = True` after it is successfully uploaded.
   - If any image fails to post during the first run (`posted = False`), it will be automatically retried in the next run.

4. **2-Factor Authentication (2FA)**
   - On your **first login**, a **2FA code** will be sent via **Email, SMS, or WhatsApp**.
   - After successful login, the software will generate and save a `session.json` file for your account.
   - For **future runs**, this session file eliminates the need to re-enter the 2FA code.

5. **Switching Devices**
   - If you change your PC or laptop, delete the `session.json` file.
   - Re-run the login process and complete 2FA again to generate a new session file.

6. **Advanced Settings via GUI**
   - You can adjust:
     - **API calling interval** (time between each API request)
     - **Post delay time** (delay between consecutive posts)
    
contact me: https://www.fiverr.com/s/38leBWY

---

For best results, ensure all image filenames in the CSV match the files in the `Images` folder exactly.
Create a new session for every New Account Just Change the name of Session file.

Enjoy automated posting! 🚀
