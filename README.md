# WaziGov ![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)

**WaziGov** is a platform that empowers women and marginalized communities in Uganda by transforming complex government documents, such as budget papers, into clear, concise summaries. Available in English and Swahili (with plans for Luganda), these summaries highlight gender equality and social inclusion, aligning with Sustainable Development Goals (SDG 5 and SDG 10). WaziGov also supports fact-checking and is developing voice transcription to ensure accessibility for users with low literacy or visual impairments.

**Tagline:** *Simplifying Rights for Women, Loud and Clear*

---

## Table of Contents

- [Features](#features)
- [Installation](#installation)
- [Usage](#usage)
- [Project Structure](#project-structure)
- [Technologies](#technologies)
- [Contributing](#contributing)
- [License](#license)
- [Contact](#contact)

---

## Features

- **Document Summarization:** Converts government PDFs (e.g., Uganda’s National Budget Framework Paper) into 100–200 character summaries, focusing on women’s rights and social equity.
- **Multilingual Support:** Summaries in English and Swahili, with plans to add Luganda and other local languages.
- **Fact-Checking:** Verifies summary accuracy with synced document metadata.
- **Accessibility:** Upcoming voice transcription feature for audio summaries, supporting low-literacy and visually impaired users.
- **API Access:** Provides endpoints (e.g., `/summaries/?region=UG&language=en`) for programmatic access to summaries.
- **Admin Interface:** Secure Django admin panel for uploading and managing documents.

---

## Installation

To run WaziGov locally:

### 1. Clone the Repository

```bash
git clone https://github.com/ma-za-kpe/EasyGov.git
cd EasyGov
```

### 2. Set Up Environment Variables

Create a `.env` file in the project root:

```env
DJANGO_SECRET_KEY=your-secret-key
DB_PASSWORD=your-secure-password
HF_TOKEN=your-huggingface-token
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0
DATABASE_URL=postgres://
```

### 3. Install Dependencies

Ensure Docker and Docker Compose are installed.

Then build and start services:

```bash
docker-compose up --build
```

### 4. Run Migrations

```bash
docker-compose exec web python manage.py migrate
```

### 5. Collect Static Files

```bash
docker-compose exec web python manage.py collectstatic --noinput
```

### 6. Create a Superuser

```bash
docker-compose exec web python manage.py createsuperuser
```

---

## Usage

### Access the Admin Interface

Visit [http://localhost:8000/admin/](http://localhost:8000/admin/) and log in with your superuser credentials.

### Add a Document

- **Title:** e.g., “2025 National Budget”
- **PDF URL:** e.g., `https://www.finance.go.ug/sites/default/files/2025-01/National%20Budget%20Framework%20Paper%20FY%202025-26.pdf`
- **Region:** Select “UG” (Uganda)
- **Should Summarize:** Check this to trigger summarization

### View Summaries

Once processed, summaries appear under the document’s details in the admin panel.

**Access via API:**  
[http://localhost:8000/summaries/?region=UG&language=en](http://localhost:8000/summaries/?region=UG&language=en)

### Deployed Version

Visit the live site at:  
[https://easygov.onrender.com/](https://easygov.onrender.com/) *(admin access required)*

**API Endpoint:**  
[https://easygov.onrender.com/summaries/?region=UG&language=en](https://easygov.onrender.com/summaries/?region=UG&language=en)

---

## Project Structure

```
EasyGov/
├── core/
│   ├── models.py          # Document, Summary, FactCheck models
│   ├── tasks.py           # Celery tasks for summarization
│   ├── summarizer.py      # NLP summarization logic
│   ├── urls.py            # API routes
├── app/
│   ├── settings.py        # Django settings
│   ├── urls.py            # Main URL configuration
├── templates/             # HTML templates
├── Dockerfile             # Docker configuration
├── docker-compose.yml     # Local development setup
├── render.yaml            # Render deployment configuration
├── requirements.txt       # Python dependencies
├── LICENSE                # MIT License
├── README.md              # Project documentation
```

---

## Technologies

- **Languages:** Python, HTML/CSS, JavaScript *(planned)*
- **Frameworks/Libraries:** Django, Celery, Hugging Face Transformers, pdfplumber, PyTorch, gunicorn, psutil
- **Platforms:** Render, Docker, GitHub
- **Cloud Services:** Render Web Service, Render Private Service, Render Redis, Render PostgreSQL
- **Databases:** PostgreSQL, Redis
- **APIs:** Hugging Face API, Text-to-Speech API *(planned)*
- **Tools:** Docker Compose, Requests, tempfile, logging, re, git, Render Dashboard, Markdown

---

## Contributing

We welcome contributions to WaziGov!

### Steps:

1. **Fork the Repository:**

```bash
git clone https://github.com/ma-za-kpe/EasyGov.git
```

2. **Create a Branch:**

```bash
git checkout -b feature/your-feature
```

3. **Make Changes and Test Locally:**

```bash
docker-compose up --build
```

4. **Submit a Pull Request:**

Push to your fork and open a PR on GitHub. Include a description of your changes and how they align with WaziGov’s mission.

Please follow our `CODE_OF_CONDUCT.md` and ensure tests pass (add tests in `core/tests.py` if needed).

---

## License

WaziGov is open source and licensed under the [MIT License](LICENSE).  
This allows anyone to use, modify, and distribute the code, provided the copyright
notice and permission notice are included.

![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)

MIT License

Copyright (c) 2025 [Your Name or Team Name]

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

---

## Contact

For questions, feedback, or collaboration, open an issue on GitHub or contact the WaziGov Team at **makpalyy@gmail.com**.