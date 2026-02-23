├── admin.py                                    # Simpy
├── api
│   ├── executor_views.py
│   ├── filters.py
│   ├── __init__.py
│   ├── serializers.py                           # Simpy
│   ├── urls.py
│   ├── urls_v1.py
│   ├── utilities.py                             # Simpy
│   └── views.py                                 # Simpy
├── apps.py                                      # Simpy
├── base
│   ├── __init__.py
│   └── models.py
├── exceptions.py
├── filters.py
├── forms.py                                     # Simpy
├── handlers.py
├── __init__.py
├── migrations
│   └── __init__.py
├── models.py
├── private_storage
│   └── storage.py
├── settings.py
├── signals.py
├── static
│   ├── guidelines
│   │   ├── test_script_guidelines.docx
│   │   └── test_script_guidelines.txt
│   ├── logo
│   │   └── NBL_Logo_rgb.png
│   └── test-management
│       ├── css
│       │   ├── device_group_form.css
│       │   ├── json_file_handler.css
│       │   ├── testcase_admin.css
│       │   ├── test-suite-admin.css
│       │   ├── test_suite_execution_form.css
│       │   └── test_suite_form.css
│       └── js
│           ├── device_group_form.js
│           ├── json_file_handler.js
│           ├── selection_toggle.js
│           ├── testcase_id_check.js
│           ├── testcase_toggle_scripts-ashutosh.js
│           ├── testcase_toggle_scripts.js
│           ├── test-suite-admin.js
│           ├── test_suite_dynamic.js
│           ├── test_suite_execution_form.js
│           └── test_suite_form.js
├── swapper.py
├── tasks.py
├── tasks_without_ssh.py
├── templates
│   ├── admin
│   │   └── test_management
│   │       ├── config_push.html
│   │       ├── import_export
│   │       │   └── testcase
│   │       │       └── change_list.html
│   │       ├── mass_execution.html
│   │       ├── testdevicegroup
│   │       │   └── change_form.html
│   │       ├── testexecution
│   │       │   ├── all_executions_history.html
│   │       │   ├── execution_history1.html
│   │       │   ├── execution_history_allure_report.html
│   │       │   └── execution_history.html
│   │       ├── testsuite
│   │       │   └── change_form.html
│   │       └── testsuitexecution
│   │           ├── change_form.html
│   │           └── execute_later.html
│   ├── email
│   │   ├── execution_report_email.html
│   │   └── execution_report_email_v1.html
│   └── reversion
│       └── recover_form.html
├── urls.py
└── utils.py                                     # Simpy
