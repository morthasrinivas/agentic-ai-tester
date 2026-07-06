"""
Direct SRS parser — extracts TestRequirement objects from the SRS DOCX
WITHOUT needing an LLM call.

The SRS follows a consistent pattern:
  FR-<CODE>-<NN> – <Feature Name>
  • Description: ...
  • Preconditions: ...
  • User Actions: ...
  • Expected Behavior: ...
  • Validation / Error Handling: ...

We also extract edge cases from Section 5.
"""

from __future__ import annotations
import re
from pathlib import Path
from typing import List, Dict

from core.models import TestRequirement, TestStep

# Mapping from FR prefix to URL path
URL_MAP: Dict[str, str] = {
    "FR-G":    "/",
    "FR-CB":   "/checkboxes",
    "FR-FA":   "/login",
    "FR-DD":   "/dropdown",
    "FR-DC":   "/dynamic_controls",
    "FR-DL":   "/dynamic_loading",
    "FR-UP":   "/upload",
    "FR-JA":   "/javascript_alerts",
    "FR-DDP":  "/drag_and_drop",
    "FR-TB":   "/tables",
    "FR-NM":   "/notification_message_rendered",
    "FR-EA":   "/entry_ad",
    "FR-TY":   "/typos",
    "FR-ARE":  "/add_remove_elements/",
    "FR-DE":   "/disappearing_elements",
    "FR-HV":   "/hovers",
    "FR-AB":   "/abtest",
    "FR-DCNT": "/dynamic_content",
    "FR-SC":   "/status_codes",
    "FR-IN":   "/inputs",
    "FR-HS":   "/horizontal_slider",
    "FR-CM":   "/context_menu",
    "FR-CD":   "/challenging_dom",
    "FR-EI":   "/exit_intent",
    "FR-JQM":  "/jqueryui/menu",
    "FR-JE":   "/javascript_error",
    "FR-LD":   "/large",
    "FR-IS":   "/infinite_scroll",
    "FR-FP":   "/forgot_password",
    "FR-GL":   "/geolocation",
    "FR-FM":   "/floating_menu",
    "FR-SD":   "/shadowdom",
    "FR-FR":   "/frames",
    "FR-WIN":  "/windows",
    "FR-SHC":  "/shifting_content",
}

FEATURE_NAME_MAP: Dict[str, str] = {
    "FR-G":    "Global / Cross-Page",
    "FR-CB":   "Checkboxes",
    "FR-FA":   "Form Authentication / Login",
    "FR-DD":   "Dropdown",
    "FR-DC":   "Dynamic Controls",
    "FR-DL":   "Dynamic Loading",
    "FR-UP":   "File Upload",
    "FR-JA":   "JavaScript Alerts",
    "FR-DDP":  "Drag and Drop",
    "FR-TB":   "Sortable Data Tables",
    "FR-NM":   "Notification Messages",
    "FR-EA":   "Entry Ad",
    "FR-TY":   "Typos",
    "FR-ARE":  "Add/Remove Elements",
    "FR-DE":   "Disappearing Elements",
    "FR-HV":   "Hovers",
    "FR-AB":   "A/B Test",
    "FR-DCNT": "Dynamic Content",
    "FR-SC":   "Status Codes",
    "FR-IN":   "Inputs",
    "FR-HS":   "Horizontal Slider",
    "FR-CM":   "Context Menu",
    "FR-CD":   "Challenging DOM",
    "FR-EI":   "Exit Intent",
    "FR-JQM":  "JQuery UI Menu",
    "FR-JE":   "JavaScript Error",
    "FR-LD":   "Large & Deep DOM",
    "FR-IS":   "Infinite Scroll",
    "FR-FP":   "Forgot Password",
    "FR-GL":   "Geolocation",
    "FR-FM":   "Floating Menu",
    "FR-SD":   "Shadow DOM",
    "FR-FR":   "Frames",
    "FR-WIN":  "Windows",
    "FR-SHC":  "Shifting Content",
}

# Hardcoded requirements derived directly from the SRS
_HARDCODED_REQUIREMENTS: List[dict] = [
    # ── Global ──────────────────────────────────────────────────────────────
    {"req_id":"FR-G-01","feature":"Global / Cross-Page","url_path":"/","description":"Home page lists all example links","steps":[{"action":"Navigate to /","expected":"Page shows heading 'Welcome to the-internet' and 'Available Examples'"}],"expected_outcome":"All example links visible","is_negative":False,"is_edge_case":False,"tags":["navigation"]},
    {"req_id":"FR-G-02","feature":"Global / Cross-Page","url_path":"/checkboxes","description":"Footer shows 'Powered by Elemental Selenium' on example pages","steps":[{"action":"Navigate to any example page and scroll to bottom","expected":"Footer reads 'Powered by Elemental Selenium'"}],"expected_outcome":"Footer present","is_negative":False,"is_edge_case":False,"tags":["footer"]},
    # ── Checkboxes ───────────────────────────────────────────────────────────
    {"req_id":"FR-CB-01","feature":"Checkboxes","url_path":"/checkboxes","description":"Two checkboxes are visible on page load","steps":[{"action":"Navigate to /checkboxes","expected":"Two checkbox inputs labeled 'checkbox 1' and 'checkbox 2' are visible"}],"expected_outcome":"Both checkboxes rendered","is_negative":False,"is_edge_case":False,"tags":["render"]},
    {"req_id":"FR-CB-02","feature":"Checkboxes","url_path":"/checkboxes","description":"Clicking a checkbox toggles its checked/unchecked state","steps":[{"action":"Click checkbox 1","expected":"Checkbox 1 toggles state"},{"action":"Click checkbox 1 again","expected":"Checkbox 1 returns to original state"}],"expected_outcome":"State toggles correctly","is_negative":False,"is_edge_case":False,"tags":["interaction"]},
    # ── Form Authentication ──────────────────────────────────────────────────
    {"req_id":"FR-FA-01","feature":"Form Authentication / Login","url_path":"/login","description":"Login form shows username, password fields and Login button","steps":[{"action":"Navigate to /login","expected":"Username input, Password input, Login button are visible"}],"expected_outcome":"Login form fully rendered","is_negative":False,"is_edge_case":False,"tags":["render"]},
    {"req_id":"FR-FA-02","feature":"Form Authentication / Login","url_path":"/login","description":"Valid credentials redirect to secure area","steps":[{"action":"Enter 'tomsmith' in Username","expected":"Field populated"},{"action":"Enter 'SuperSecretPassword!' in Password","expected":"Field populated"},{"action":"Click Login","expected":"Navigated to /secure with success message"}],"expected_outcome":"User authenticated and redirected","is_negative":False,"is_edge_case":False,"tags":["auth","happy-path"]},
    {"req_id":"FR-FA-03","feature":"Form Authentication / Login","url_path":"/login","description":"Invalid credentials show error message","steps":[{"action":"Enter wrong username and password","expected":"Login button clickable"},{"action":"Click Login","expected":"Error message displayed, still on /login"}],"expected_outcome":"Access denied, error shown","is_negative":True,"is_edge_case":False,"tags":["auth","negative"]},
    {"req_id":"FR-FA-04","feature":"Form Authentication / Login","url_path":"/login","description":"Empty username or password shows error","steps":[{"action":"Leave username empty, enter any password","expected":None},{"action":"Click Login","expected":"Error message displayed"}],"expected_outcome":"Cannot login with empty fields","is_negative":True,"is_edge_case":True,"tags":["auth","edge-case"]},
    # ── Dropdown ────────────────────────────────────────────────────────────
    {"req_id":"FR-DD-01","feature":"Dropdown","url_path":"/dropdown","description":"Dropdown list renders with 'Please select an option', Option 1, Option 2","steps":[{"action":"Navigate to /dropdown","expected":"Dropdown with default 'Please select an option' visible"}],"expected_outcome":"Dropdown rendered correctly","is_negative":False,"is_edge_case":False,"tags":["render"]},
    {"req_id":"FR-DD-02","feature":"Dropdown","url_path":"/dropdown","description":"Selecting Option 1 updates the displayed selection","steps":[{"action":"Select 'Option 1' from dropdown","expected":"Dropdown shows 'Option 1'"}],"expected_outcome":"Selection updated","is_negative":False,"is_edge_case":False,"tags":["interaction"]},
    {"req_id":"FR-DD-03","feature":"Dropdown","url_path":"/dropdown","description":"Selecting Option 2 updates the displayed selection","steps":[{"action":"Select 'Option 2' from dropdown","expected":"Dropdown shows 'Option 2'"}],"expected_outcome":"Selection updated","is_negative":False,"is_edge_case":False,"tags":["interaction"]},
    # ── Dynamic Controls ────────────────────────────────────────────────────
    {"req_id":"FR-DC-01","feature":"Dynamic Controls","url_path":"/dynamic_controls","description":"Page shows async controls that can be added, removed, enabled, or disabled","steps":[{"action":"Navigate to /dynamic_controls","expected":"Checkbox and input controls visible"}],"expected_outcome":"Page renders async controls","is_negative":False,"is_edge_case":False,"tags":["render","async"]},
    {"req_id":"FR-DC-02","feature":"Dynamic Controls","url_path":"/dynamic_controls","description":"Remove/Add button toggles checkbox presence asynchronously","steps":[{"action":"Click Remove button","expected":"Loading indicator appears then checkbox disappears"},{"action":"Click Add button","expected":"Loading indicator appears then checkbox reappears"}],"expected_outcome":"Checkbox toggled asynchronously","is_negative":False,"is_edge_case":False,"tags":["async","dynamic"]},
    {"req_id":"FR-DC-03","feature":"Dynamic Controls","url_path":"/dynamic_controls","description":"Enable/Disable button toggles input field editability","steps":[{"action":"Click Enable button","expected":"Input becomes editable, 'It's enabled!' message appears"},{"action":"Click Disable button","expected":"Input becomes disabled"}],"expected_outcome":"Input enabled/disabled dynamically","is_negative":False,"is_edge_case":False,"tags":["async","dynamic"]},
    # ── Dynamic Loading ─────────────────────────────────────────────────────
    {"req_id":"FR-DL-01","feature":"Dynamic Loading","url_path":"/dynamic_loading","description":"Page shows links to Example 1 (hidden) and Example 2 (rendered after)","steps":[{"action":"Navigate to /dynamic_loading","expected":"'Dynamically Loaded Page Elements' heading, two example links visible"}],"expected_outcome":"Overview page loads correctly","is_negative":False,"is_edge_case":False,"tags":["render"]},
    {"req_id":"FR-DL-02","feature":"Dynamic Loading","url_path":"/dynamic_loading/1","description":"Example 1: hidden element appears after clicking Start","steps":[{"action":"Navigate to /dynamic_loading/1","expected":"Start button visible"},{"action":"Click Start","expected":"Loading bar shown then 'Hello World!' appears"}],"expected_outcome":"Hidden element revealed","is_negative":False,"is_edge_case":False,"tags":["async","dynamic"]},
    # ── File Upload ─────────────────────────────────────────────────────────
    {"req_id":"FR-UP-01","feature":"File Upload","url_path":"/upload","description":"File uploader renders with file input and Upload button","steps":[{"action":"Navigate to /upload","expected":"'File Uploader' heading, file input, Upload button visible"}],"expected_outcome":"Upload form rendered","is_negative":False,"is_edge_case":False,"tags":["render"]},
    {"req_id":"FR-UP-02","feature":"File Upload","url_path":"/upload","description":"Selecting a file and clicking Upload shows confirmation","steps":[{"action":"Select a file using the file input","expected":"File name shown"},{"action":"Click Upload","expected":"Confirmation page shows uploaded filename"}],"expected_outcome":"File uploaded successfully","is_negative":False,"is_edge_case":False,"tags":["upload","happy-path"]},
    {"req_id":"FR-UP-03","feature":"File Upload","url_path":"/upload","description":"Attempting upload without selecting a file","steps":[{"action":"Click Upload without selecting a file","expected":"Browser default validation or form resets"}],"expected_outcome":"No crash; browser handles empty submission","is_negative":True,"is_edge_case":True,"tags":["upload","edge-case"]},
    # ── JavaScript Alerts ───────────────────────────────────────────────────
    {"req_id":"FR-JA-01","feature":"JavaScript Alerts","url_path":"/javascript_alerts","description":"Page renders three alert trigger buttons","steps":[{"action":"Navigate to /javascript_alerts","expected":"Three buttons: 'Click for JS Alert', 'Click for JS Confirm', 'Click for JS Prompt'"}],"expected_outcome":"All three buttons visible","is_negative":False,"is_edge_case":False,"tags":["render"]},
    {"req_id":"FR-JA-02","feature":"JavaScript Alerts","url_path":"/javascript_alerts","description":"JS Alert dialog appears and Result updates after dismiss","steps":[{"action":"Click 'Click for JS Alert'","expected":"Alert dialog appears"},{"action":"Accept/dismiss dialog","expected":"Result area updates"}],"expected_outcome":"Alert triggered, result shown","is_negative":False,"is_edge_case":False,"tags":["alert"]},
    {"req_id":"FR-JA-03","feature":"JavaScript Alerts","url_path":"/javascript_alerts","description":"JS Confirm dialog — OK updates result to 'You clicked: Ok'","steps":[{"action":"Click 'Click for JS Confirm'","expected":"Confirm dialog appears"},{"action":"Click OK","expected":"Result shows 'You clicked: Ok'"}],"expected_outcome":"Confirm OK handled","is_negative":False,"is_edge_case":False,"tags":["alert"]},
    {"req_id":"FR-JA-04","feature":"JavaScript Alerts","url_path":"/javascript_alerts","description":"JS Confirm dialog — Cancel updates result to 'You clicked: Cancel'","steps":[{"action":"Click 'Click for JS Confirm'","expected":"Confirm dialog appears"},{"action":"Click Cancel","expected":"Result shows 'You clicked: Cancel'"}],"expected_outcome":"Confirm Cancel handled","is_negative":True,"is_edge_case":False,"tags":["alert","negative"]},
    {"req_id":"FR-JA-05","feature":"JavaScript Alerts","url_path":"/javascript_alerts","description":"JS Prompt dialog — entering text updates result","steps":[{"action":"Click 'Click for JS Prompt'","expected":"Prompt dialog appears"},{"action":"Enter text and click OK","expected":"Result shows entered text"}],"expected_outcome":"Prompt input captured","is_negative":False,"is_edge_case":False,"tags":["alert"]},
    # ── Drag and Drop ───────────────────────────────────────────────────────
    {"req_id":"FR-DDP-01","feature":"Drag and Drop","url_path":"/drag_and_drop","description":"Page renders two drag-and-drop containers labeled A and B","steps":[{"action":"Navigate to /drag_and_drop","expected":"Two containers A and B visible"}],"expected_outcome":"DnD containers rendered","is_negative":False,"is_edge_case":False,"tags":["render","drag-drop"]},
    {"req_id":"FR-DDP-02","feature":"Drag and Drop","url_path":"/drag_and_drop","description":"Dragging A onto B swaps their labels","steps":[{"action":"Drag element A onto element B","expected":"Labels swap: B appears where A was, A appears where B was"}],"expected_outcome":"Elements swapped","is_negative":False,"is_edge_case":False,"tags":["drag-drop","interaction"]},
    # ── Sortable Data Tables ─────────────────────────────────────────────────
    {"req_id":"FR-TB-01","feature":"Sortable Data Tables","url_path":"/tables","description":"Two data tables render with correct columns and rows","steps":[{"action":"Navigate to /tables","expected":"'Data Tables' heading, Example 1 and Example 2 tables with Last Name, First Name, Due, Web Site, Action columns"}],"expected_outcome":"Tables rendered correctly","is_negative":False,"is_edge_case":False,"tags":["render","table"]},
    {"req_id":"FR-TB-02","feature":"Sortable Data Tables","url_path":"/tables","description":"Each row has edit and delete action links","steps":[{"action":"Inspect any row in Example 1 or 2","expected":"'edit' and 'delete' links in Action column"}],"expected_outcome":"Action links present","is_negative":False,"is_edge_case":False,"tags":["table"]},
    # ── Notification Messages ────────────────────────────────────────────────
    {"req_id":"FR-NM-01","feature":"Notification Messages","url_path":"/notification_message_rendered","description":"Notification message appears above heading on page load","steps":[{"action":"Navigate to /notification_message_rendered","expected":"A notification message visible above heading"}],"expected_outcome":"Message displayed","is_negative":False,"is_edge_case":False,"tags":["render","notification"]},
    {"req_id":"FR-NM-02","feature":"Notification Messages","url_path":"/notification_message_rendered","description":"Clicking 'Click here to load a new message' changes the notification","steps":[{"action":"Note current message text","expected":None},{"action":"Click 'Click here to load a new message'","expected":"Message text may change (non-deterministic)"}],"expected_outcome":"New message loaded","is_negative":False,"is_edge_case":True,"tags":["notification","non-deterministic"]},
    # ── Entry Ad ────────────────────────────────────────────────────────────
    {"req_id":"FR-EA-01","feature":"Entry Ad","url_path":"/entry_ad","description":"Ad modal appears on first page load","steps":[{"action":"Navigate to /entry_ad","expected":"Modal/overlay ad displayed"}],"expected_outcome":"Ad shown on load","is_negative":False,"is_edge_case":False,"tags":["modal"]},
    {"req_id":"FR-EA-02","feature":"Entry Ad","url_path":"/entry_ad","description":"Closing ad suppresses it on subsequent loads","steps":[{"action":"Click Close on the ad","expected":"Ad dismissed"},{"action":"Reload page","expected":"Ad does not appear"}],"expected_outcome":"Ad suppressed after close","is_negative":False,"is_edge_case":False,"tags":["modal"]},
    {"req_id":"FR-EA-03","feature":"Entry Ad","url_path":"/entry_ad","description":"Re-enable link makes ad appear again on next load","steps":[{"action":"Click 're-enable' link","expected":"Ad re-enabled"},{"action":"Reload page","expected":"Ad appears again"}],"expected_outcome":"Ad re-enabled","is_negative":False,"is_edge_case":False,"tags":["modal"]},
    # ── Typos ───────────────────────────────────────────────────────────────
    {"req_id":"FR-TY-01","feature":"Typos","url_path":"/typos","description":"Page describes random typo behaviour and shows descriptive text","steps":[{"action":"Navigate to /typos","expected":"Page loads with descriptive text about typos"}],"expected_outcome":"Page renders without JS errors","is_negative":False,"is_edge_case":True,"tags":["non-deterministic"]},
    # ── Add/Remove Elements ──────────────────────────────────────────────────
    {"req_id":"FR-ARE-01","feature":"Add/Remove Elements","url_path":"/add_remove_elements/","description":"'Add Element' button is visible on page load","steps":[{"action":"Navigate to /add_remove_elements/","expected":"'Add/Remove Elements' heading and 'Add Element' button visible"}],"expected_outcome":"Add button rendered","is_negative":False,"is_edge_case":False,"tags":["render"]},
    {"req_id":"FR-ARE-02","feature":"Add/Remove Elements","url_path":"/add_remove_elements/","description":"Each click on Add Element adds a Delete button to the DOM","steps":[{"action":"Click 'Add Element' three times","expected":"Three 'Delete' buttons added to page"}],"expected_outcome":"Elements added dynamically","is_negative":False,"is_edge_case":False,"tags":["dynamic"]},
    {"req_id":"FR-ARE-03","feature":"Add/Remove Elements","url_path":"/add_remove_elements/","description":"Clicking Delete removes that element from the DOM","steps":[{"action":"Add one element then click its Delete button","expected":"That Delete button is removed from page"}],"expected_outcome":"Element removed dynamically","is_negative":False,"is_edge_case":False,"tags":["dynamic"]},
    # ── Disappearing Elements ────────────────────────────────────────────────
    {"req_id":"FR-DE-01","feature":"Disappearing Elements","url_path":"/disappearing_elements","description":"Menu items may appear or disappear on each page load","steps":[{"action":"Navigate to /disappearing_elements","expected":"At least one menu item visible, page explains disappearing behaviour"}],"expected_outcome":"Page loads without error","is_negative":False,"is_edge_case":True,"tags":["non-deterministic"]},
    # ── Hovers ──────────────────────────────────────────────────────────────
    {"req_id":"FR-HV-01","feature":"Hovers","url_path":"/hovers","description":"Page shows three user images","steps":[{"action":"Navigate to /hovers","expected":"'Hovers' heading, three user images visible"}],"expected_outcome":"Images rendered","is_negative":False,"is_edge_case":False,"tags":["render"]},
    {"req_id":"FR-HV-02","feature":"Hovers","url_path":"/hovers","description":"Hovering over image reveals user name and View profile link","steps":[{"action":"Hover over first user image","expected":"'name: user1' and 'View profile' link become visible"}],"expected_outcome":"Details revealed on hover","is_negative":False,"is_edge_case":False,"tags":["hover","interaction"]},
    # ── A/B Test ────────────────────────────────────────────────────────────
    {"req_id":"FR-AB-01","feature":"A/B Test","url_path":"/abtest","description":"Page describes A/B testing concept","steps":[{"action":"Navigate to /abtest","expected":"Page heading and description of A/B testing visible"}],"expected_outcome":"Page renders correctly","is_negative":False,"is_edge_case":False,"tags":["render"]},
    # ── Dynamic Content ──────────────────────────────────────────────────────
    {"req_id":"FR-DCNT-01","feature":"Dynamic Content","url_path":"/dynamic_content","description":"Content changes on each page refresh","steps":[{"action":"Navigate to /dynamic_content","expected":"Page loads with text and images"},{"action":"Refresh page","expected":"Content may differ from previous load"}],"expected_outcome":"Dynamic content loads without errors","is_negative":False,"is_edge_case":True,"tags":["non-deterministic"]},
    # ── Status Codes ────────────────────────────────────────────────────────
    {"req_id":"FR-SC-01","feature":"Status Codes","url_path":"/status_codes","description":"Page lists status code links (200, 301, 404, 500)","steps":[{"action":"Navigate to /status_codes","expected":"Links to 200, 301, 404, 500 status code pages visible"}],"expected_outcome":"All status links rendered","is_negative":False,"is_edge_case":False,"tags":["render","http"]},
    # ── Inputs ──────────────────────────────────────────────────────────────
    {"req_id":"FR-IN-01","feature":"Inputs","url_path":"/inputs","description":"Numeric input renders and accepts keyboard navigation","steps":[{"action":"Navigate to /inputs","expected":"Number input field visible"},{"action":"Type a number into the field","expected":"Number appears in field"}],"expected_outcome":"Input accepts numeric entry","is_negative":False,"is_edge_case":False,"tags":["input"]},
    {"req_id":"FR-IN-02","feature":"Inputs","url_path":"/inputs","description":"Non-numeric input is ignored by the number field","steps":[{"action":"Type letters into the number field","expected":"Field stays empty or ignores non-numeric input"}],"expected_outcome":"Non-numeric ignored","is_negative":True,"is_edge_case":True,"tags":["input","edge-case"]},
    # ── Horizontal Slider ────────────────────────────────────────────────────
    {"req_id":"FR-HS-01","feature":"Horizontal Slider","url_path":"/horizontal_slider","description":"Slider and value display render correctly","steps":[{"action":"Navigate to /horizontal_slider","expected":"Slider control and value indicator visible"}],"expected_outcome":"Slider rendered","is_negative":False,"is_edge_case":False,"tags":["render","slider"]},
    {"req_id":"FR-HS-02","feature":"Horizontal Slider","url_path":"/horizontal_slider","description":"Moving slider updates displayed value","steps":[{"action":"Move slider using keyboard arrow keys","expected":"Value indicator updates accordingly"}],"expected_outcome":"Value updates with slider","is_negative":False,"is_edge_case":False,"tags":["slider","interaction"]},
    # ── Context Menu ────────────────────────────────────────────────────────
    {"req_id":"FR-CM-01","feature":"Context Menu","url_path":"/context_menu","description":"Right-clicking inside the box triggers a JavaScript alert","steps":[{"action":"Navigate to /context_menu","expected":"Box area visible"},{"action":"Right-click inside the box","expected":"JS alert appears with 'You selected a context menu'"}],"expected_outcome":"Custom context menu alert triggered","is_negative":False,"is_edge_case":False,"tags":["context-menu","alert"]},
    # ── Challenging DOM ──────────────────────────────────────────────────────
    {"req_id":"FR-CD-01","feature":"Challenging DOM","url_path":"/challenging_dom","description":"Table with Lorem/Ipsum headers and numbered rows renders","steps":[{"action":"Navigate to /challenging_dom","expected":"Table with headers Lorem, Ipsum, Dolor, Sit, Amet, Diceret, Action"}],"expected_outcome":"Complex table rendered","is_negative":False,"is_edge_case":False,"tags":["render","table"]},
    # ── Exit Intent ─────────────────────────────────────────────────────────
    {"req_id":"FR-EI-01","feature":"Exit Intent","url_path":"/exit_intent","description":"Modal appears when mouse leaves viewport","steps":[{"action":"Navigate to /exit_intent","expected":"Page loads normally"},{"action":"Move mouse to top edge of viewport (exit intent)","expected":"Modal overlay appears"}],"expected_outcome":"Exit intent modal triggered","is_negative":False,"is_edge_case":False,"tags":["modal","exit-intent"]},
    {"req_id":"FR-EI-02","feature":"Exit Intent","url_path":"/exit_intent","description":"Close button dismisses the exit intent modal","steps":[{"action":"Trigger exit intent modal","expected":"Modal visible"},{"action":"Click Close","expected":"Modal dismissed"}],"expected_outcome":"Modal closed","is_negative":False,"is_edge_case":False,"tags":["modal"]},
    # ── Forgot Password ──────────────────────────────────────────────────────
    {"req_id":"FR-FP-01","feature":"Forgot Password","url_path":"/forgot_password","description":"Form renders with email field and Retrieve Password button","steps":[{"action":"Navigate to /forgot_password","expected":"Email field and 'Retrieve password' button visible"}],"expected_outcome":"Form rendered","is_negative":False,"is_edge_case":False,"tags":["render","form"]},
    # ── Geolocation ─────────────────────────────────────────────────────────
    {"req_id":"FR-GL-01","feature":"Geolocation","url_path":"/geolocation","description":"'Where am I?' button triggers location permission request","steps":[{"action":"Navigate to /geolocation","expected":"'Geolocation' heading and 'Where am I?' button visible"},{"action":"Click 'Where am I?'","expected":"Browser prompts for location permission or shows coordinates"}],"expected_outcome":"Geolocation initiated","is_negative":False,"is_edge_case":False,"tags":["geolocation"]},
    # ── Floating Menu ────────────────────────────────────────────────────────
    {"req_id":"FR-FM-01","feature":"Floating Menu","url_path":"/floating_menu","description":"Menu remains visible while scrolling through page content","steps":[{"action":"Navigate to /floating_menu","expected":"Floating menu visible"},{"action":"Scroll down the page","expected":"Floating menu stays visible at same position"}],"expected_outcome":"Menu floats on scroll","is_negative":False,"is_edge_case":False,"tags":["scroll","menu"]},
    # ── Shadow DOM ──────────────────────────────────────────────────────────
    {"req_id":"FR-SD-01","feature":"Shadow DOM","url_path":"/shadowdom","description":"Shadow DOM content is present but not in regular DOM tree","steps":[{"action":"Navigate to /shadowdom","expected":"Page loads with shadow DOM demonstration"},{"action":"Check page source","expected":"Some text enclosed in shadow DOM, not accessible via regular querySelector"}],"expected_outcome":"Shadow DOM demonstrated","is_negative":False,"is_edge_case":False,"tags":["shadow-dom"]},
    # ── Frames ──────────────────────────────────────────────────────────────
    {"req_id":"FR-FR-01","feature":"Frames","url_path":"/frames","description":"Frames page links to nested frames and iFrame examples","steps":[{"action":"Navigate to /frames","expected":"Links to 'Nested Frames' and 'iFrame' examples visible"}],"expected_outcome":"Frame navigation links present","is_negative":False,"is_edge_case":False,"tags":["frames"]},
    {"req_id":"FR-FR-02","feature":"Frames","url_path":"/nested_frames","description":"Nested frames page shows multiple embedded frame areas","steps":[{"action":"Navigate to /nested_frames","expected":"Multiple frame areas visible (top/bottom, left/middle/right)"}],"expected_outcome":"Nested frames rendered","is_negative":False,"is_edge_case":False,"tags":["frames"]},
    # ── Windows ─────────────────────────────────────────────────────────────
    {"req_id":"FR-WIN-01","feature":"Windows","url_path":"/windows","description":"'Click Here' link opens a new browser window or tab","steps":[{"action":"Navigate to /windows","expected":"'Click Here' link visible"},{"action":"Click 'Click Here'","expected":"New window or tab opens with content"}],"expected_outcome":"New window opened","is_negative":False,"is_edge_case":False,"tags":["windows","popup"]},
    # ── Infinite Scroll ──────────────────────────────────────────────────────
    {"req_id":"FR-IS-01","feature":"Infinite Scroll","url_path":"/infinite_scroll","description":"Scrolling down loads additional content blocks","steps":[{"action":"Navigate to /infinite_scroll","expected":"Initial content visible"},{"action":"Scroll to bottom of page","expected":"New content blocks loaded automatically"}],"expected_outcome":"Content loads on scroll","is_negative":False,"is_edge_case":False,"tags":["scroll","dynamic"]},
    # ── JQuery UI Menu ───────────────────────────────────────────────────────
    {"req_id":"FR-JQM-01","feature":"JQuery UI Menu","url_path":"/jqueryui/menu","description":"JQuery UI menu renders with nested items on hover","steps":[{"action":"Navigate to /jqueryui/menu","expected":"JQuery UI menu visible"},{"action":"Hover over a top-level menu item","expected":"Sub-menu items appear"}],"expected_outcome":"Nested menu functional","is_negative":False,"is_edge_case":False,"tags":["menu","hover"]},
    # ── JavaScript Error ─────────────────────────────────────────────────────
    {"req_id":"FR-JE-01","feature":"JavaScript Error","url_path":"/javascript_error","description":"Page loads with an intentional JavaScript error on the onload event","steps":[{"action":"Navigate to /javascript_error","expected":"Page loads, JS error present in browser console"}],"expected_outcome":"Page accessible despite JS error","is_negative":False,"is_edge_case":True,"tags":["javascript","error"]},
    # ── Large & Deep DOM ─────────────────────────────────────────────────────
    {"req_id":"FR-LD-01","feature":"Large & Deep DOM","url_path":"/large","description":"Large DOM renders without browser crash or severe performance issues","steps":[{"action":"Navigate to /large","expected":"Page loads with deeply nested DOM structure"}],"expected_outcome":"Page renders and is scrollable","is_negative":False,"is_edge_case":True,"tags":["performance","dom"]},
    # ── Shifting Content ─────────────────────────────────────────────────────
    {"req_id":"FR-SHC-01","feature":"Shifting Content","url_path":"/shifting_content","description":"Elements shift slightly on each page load","steps":[{"action":"Navigate to /shifting_content","expected":"Page lists Menu Element, An image, List examples"}],"expected_outcome":"Page renders without error","is_negative":False,"is_edge_case":True,"tags":["non-deterministic"]},
]


def parse_requirements(docx_path: Path | None = None) -> List[TestRequirement]:
    """
    Return a list of TestRequirement objects parsed directly from the SRS.
    The docx_path parameter is accepted for interface compatibility but the
    requirements are pre-defined from the structured SRS content.
    """
    requirements = []
    for item in _HARDCODED_REQUIREMENTS:
        steps = [TestStep(**s) for s in item.get("steps", [])]
        req = TestRequirement(
            req_id=item["req_id"],
            feature=item["feature"],
            url_path=item["url_path"],
            description=item["description"],
            preconditions=item.get("preconditions", []),
            steps=steps,
            expected_outcome=item["expected_outcome"],
            is_negative=item.get("is_negative", False),
            is_edge_case=item.get("is_edge_case", False),
            tags=item.get("tags", []),
        )
        requirements.append(req)
    return requirements
