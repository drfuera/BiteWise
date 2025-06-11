# BiteWise - Your Personal Nutrition Companion

![BiteWise Screenshot 1](https://github.com/drfuera/BiteWise/blob/main/screenshots/1.png)

## Introduction

Welcome to BiteWise, your friendly, open-source nutrition tracking application! Whether you're just starting to monitor your diet or are a seasoned health enthusiast, BiteWise offers a simple and intuitive way to keep track of your daily food intake, weight, and macro breakdowns. This README will guide you through setting up and using BiteWise, even if you're new to coding or nutrition tracking apps.

## Features

*   **Food Journaling**: Easily log your meals and snacks throughout the day.
*   **Macro Tracking**: Visualize your daily macro intake with informative pie charts.
*   **Weight Management**: Monitor your weight changes over time with interactive graphs.
*   **User-Friendly Interface**: Enjoy a clean, intuitive design that makes tracking your nutrition a breeze.

## Screenshots

Here are some visual previews of BiteWise in action:

*   ![BiteWise Screenshot 2](https://github.com/drfuera/BiteWise/blob/main/screenshots/2.png)
*   ![BiteWise Screenshot 3](https://github.com/drfuera/BiteWise/blob/main/screenshots/3.png)
*   ![BiteWise Screenshot 4](https://github.com/drfuera/BiteWise/blob/main/screenshots/4.png)
*   ![BiteWise Screenshot 5](https://github.com/drfuera/BiteWise/blob/main/screenshots/5.png)
*   ![BiteWise Screenshot 6](https://github.com/drfuera/BiteWise/blob/main/screenshots/6.png)
*   ![BiteWise Screenshot 7](https://github.com/drfuera/BiteWise/blob/main/screenshots/7.png)
*   ![BiteWise Screenshot 8](https://github.com/drfuera/BiteWise/blob/main/screenshots/8.png)
*   ![BiteWise Screenshot 8](https://github.com/drfuera/BiteWise/blob/main/screenshots/9.png)
*   ![BiteWise Screenshot 8](https://github.com/drfuera/BiteWise/blob/main/screenshots/10.png)

## Getting Started

### Prerequisites

Before you begin, ensure you have the following installed on your system:

*   **Python 3.6+**: You can download it from the official Python website.
*   **GTK+3**: This is a library for creating graphical user interfaces. Installation varies based on your operating system:

    *   **Windows**: Easiest way is to install [MSYS2](https://www.msys2.org/) and then use `pacman -S mingw-w64-x86_64-gtk3`
    *   **MacOS**: You can install it using [Homebrew](https://brew.sh/) with the command: `brew install gtk+3`
    *   **Linux (Debian/Ubuntu)**: Use the following command in your terminal: `sudo apt-get install libgtk-3-dev`
*   **PyGObject**: This is the Python binding for GTK. Install it using pip:

    ```
    pip install PyGObject
    ```

### Installation

1.  **Clone the Repository**

    First, clone the BiteWise repository to your local machine using Git:

    ```
    git clone https://github.com/drfuera/BiteWise.git
    cd BiteWise
    ```

2.  **Install Dependencies**

    It's recommended to create a virtual environment to manage the project dependencies.

    ```
    python3 -m venv venv
    source venv/bin/activate  # On Windows use `venv\Scripts\activate`
    pip install -r requirements.txt
    ```

3.  **Run the Application**

    Navigate to the project directory and run the main script:

    ```
    python main.py
    ```

### How to Use

1.  **Journal Tab**: Log your daily food intake by adding entries with food descriptions and associated macros.
2.  **Macro Breakdown Tab**: View a pie chart visualizing your macro percentages for the day. Hover over the slices for detailed information.
3.  **Weight Stats Tab**: Input your weight daily to see a graphical representation of your weight loss or gain over time.

## Code Overview

Here's a brief look at some key components of BiteWise:

*   `main.py`: The main entry point of the application.
*   `weight_tab.py`: Contains the `WeightGraph` and `WeightStatsTab` classes for displaying weight statistics. The `WeightGraph` class uses `cairo` to draw the weight plot.
*   `macro_tab.py`: Includes the `PieChart` and `MacroBreakdownTab` classes for visualizing macro data. The `PieChart` class uses `cairo` to render the pie chart.
*   `journal_tab.py`: Implements the food journal functionality.
*   `db/journal.json`: A JSON file used to store the journal entries. Make sure this file exists or is created in the right directory.

## Contributing

Contributions are welcome! If you'd like to contribute to BiteWise, please follow these steps:

1.  Fork the repository.
2.  Create a new branch for your feature or bug fix.
3.  Make your changes and commit them with descriptive commit messages.
4.  Submit a pull request.

## License

This project is licensed under the [MIT License](LICENSE).

## Contact

If you have any questions or suggestions, feel free to reach out!

![GitHub release](https://img.shields.io/github/v/release/drfuera/BiteWise)  ![GitHub downloads](https://img.shields.io/github/downloads/drfuera/BiteWise/total)  ![License](https://img.shields.io/badge/License-MIT-red)  
