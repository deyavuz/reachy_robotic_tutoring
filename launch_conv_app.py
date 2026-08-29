import sys
import gstreamer_libs
gstreamer_libs.setup_python_environment()
from reachy_mini_conversation_app.main import main
if __name__ == "__main__":
    sys.exit(main())
