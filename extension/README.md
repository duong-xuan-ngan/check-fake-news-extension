# How to Build and Run the Extension

## 1. Build the Extension
Steps to perform:
1. Open the terminal and navigate to the `sidepanel-src` directory:
   ```bash
   cd sidepanel-src
   ```
2. Install Node.js dependencies (if not installed yet):
   ```bash
   npm install
   ```
3. Run the build command:
   ```bash
   npm run build
   ```

## 2. Install the Extension in Chrome

1. Open the Chrome browser.
2. Go to the Extensions management page by typing this address into the URL bar: `chrome://extensions/`
3. In the top right corner, toggle on **Developer mode**.
4. Click the **Load unpacked** button that appears in the top left corner.
5. Select the `extension` folder (located directly in your project root `check-fake-new-extension`).

## 3. How to Use the Extension
- Ensure the backend server is running.
- Navigate to any regular webpage. Note that extensions do not work on internal `chrome://` pages.
- Highlight any text or news snippet you want to verify.
- Right-click on the highlighted text and select the option from the context menu (e.g., Analyze with Fake News Checker).
- The extension's side panel will open automatically and send the data to the backend for analysis.
