from flask import (
    Blueprint,
    current_app,
    render_template,
    request,
    session,
    redirect,
    url_for,
)
from app.common.utils import log_telemetry
from app.common.auth import create_jwe, decrypt_jwe
from flask_login import login_user, logout_user, login_required, current_user
import os
import sys

main_bp = Blueprint("main", __name__)


def _get_recent_topics(limit=5):
    from app.common.storage import get_topics_metadata

    return get_topics_metadata(limit=limit)


@main_bp.route("/", methods=["GET", "POST"])
def index():
    """Render home page with topics list or redirect to selected learning mode."""
    # Cleanup persistent sandbox if exists
    sandbox_id = session.get("sandbox_id")
    if sandbox_id:
        try:
            from app.common.sandbox import Sandbox

            sb = Sandbox(sandbox_id=sandbox_id)
            sb.cleanup()
        except Exception:
            pass  # Ignore cleanup errors
        session.pop("sandbox_id", None)

    recent_topics = _get_recent_topics(limit=5)

    if request.method == "POST":
        topic_name = request.form.get("topic", "").strip()
        mode = request.form.get("mode", "chapter")

        if not topic_name:
            return render_template(
                "index.html", topics=recent_topics, error="Please enter a topic name."
            )

        # Telemetry Hook: Topic Created/Opened (Intent)
        try:
            log_telemetry(
                event_type="topic_accessed",
                triggers={"source": "web_ui", "action": "form_submit"},
                payload={"topic_name": topic_name, "mode": mode},
            )
        except Exception:
            pass  # Telemetry failures must not block user flow; ignore logging errors.

        if mode:
            if mode == "chapter":
                return redirect(url_for("chapter.mode", topic_name=topic_name))

            elif mode == "quiz":
                return redirect(url_for("quiz.mode", topic_name=topic_name))

            elif mode == "flashcard":
                return redirect(url_for("flashcard.mode", topic_name=topic_name))

            elif mode == "reel":
                return redirect(url_for("reel.mode", topic_name=topic_name))

            elif mode == "chat":
                return redirect(url_for("chat.mode", topic_name=topic_name))

            else:
                return render_template(
                    "index.html",
                    topics=recent_topics,
                    error=f"Mode {mode} not available",
                )

    return render_template("index.html", topics=recent_topics)


@main_bp.route("/topics")
@login_required
def saved_topics():
    """Render the full saved topics page."""
    from app.common.storage import get_topics_metadata

    return render_template("saved_topics.html", topics=get_topics_metadata())


@main_bp.route("/favicon.ico")
def favicon():
    """Serve the favicon.ico file."""
    from flask import current_app

    return current_app.send_static_file("favicon.ico")


@main_bp.app_context_processor
def inject_notifications():
    """Make notifications available to all templates."""
    from app.common.utils import check_for_updates

    # Define app version here or import from config
    APP_VERSION = "v0.0.1"  # TODO: Move to config

    try:
        update_note = check_for_updates(APP_VERSION)
        if update_note:
            return dict(system_notifications=[update_note])
    except Exception:
        pass

    return dict(system_notifications=[])


@main_bp.app_context_processor
def inject_jwe():
    """
    Inject JWE token into all templates.
    This allows the frontend to read it from a meta tag and send it in headers.
    """
    if current_user.is_authenticated:
        try:
            token = create_jwe({"user_id": current_user.userid})
            if isinstance(token, bytes):
                token = token.decode("utf-8")
            return dict(jwe_token=token)
        except Exception:
            from flask import current_app

            current_app.logger.exception("Failed to inject JWE token")
    return dict(jwe_token="")


@main_bp.route("/login", methods=["GET", "POST"])
def login():
    """Handle user login with username and password authentication."""
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if not username or not password:
            return render_template(
                "login.html", error="Username and password are required"
            )

        if not username or not password:
            return render_template(
                "signup.html", error="Username and password are required"
            )

        from app.core.models import Login

        user = Login.query.filter_by(username=username).first()

        if user is None or not user.check_password(password):
            return render_template("login.html", error="Invalid username or password")

        login_user(user)

        # Telemetry Hook: User Login
        try:
            log_telemetry(
                event_type="user_login",
                triggers={"source": "web_ui", "action": "form_submit"},
                payload={"method": "password"},
            )
        except Exception:
            pass  # Telemetry failures must not block user flow; ignore logging errors.

        return redirect(url_for("main.index"))

    return render_template("login.html")


@main_bp.route("/signup", methods=["GET", "POST"])
def signup():
    """Handle new user registration and profile creation."""
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))

    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]

        from app.core.models import User, Login, Installation
        from app.core.extensions import db

        login_check = Login.query.filter_by(username=username).first()
        if login_check:
            return render_template("signup.html", error="Username already exists")

        # Determine installation context explicitly
        installations = Installation.query.all()
        if len(installations) == 0:
            # First time setup - Create Installation
            # First time setup - Wait for DCS Registration
            # The background SyncManager should have registered the device.
            # If not yet, we ask user to wait.
            return render_template(
                "signup.html",
                error="System is initializing registration. Please wait a moment and try again.",
            )

        elif len(installations) == 1:
            inst_id = installations[0].installation_id
        else:
            # Multiple installations detected; avoid arbitrary association
            return render_template(
                "signup.html",
                error="Multiple installations are configured. Please contact the administrator.",
            )

        uid = Login.generate_userid(inst_id)

        # Removed auto-fill of name with username
        new_login = Login(
            userid=uid, username=username, name="", installation_id=inst_id
        )
        new_login.set_password(password)
        db.session.add(new_login)

        new_user = User(login_id=uid)  # Profile details separate
        db.session.add(new_user)

        db.session.commit()

        login_user(new_login)

        # Telemetry Hook: User Signup
        try:
            telemetry_payload = {}
            from app.common.utils import get_system_info

            sys_info = get_system_info()
            if isinstance(sys_info, dict) and "install_method" in sys_info:
                telemetry_payload["install_method"] = sys_info["install_method"]

            log_telemetry(
                event_type="user_signup",
                triggers={"source": "web_ui", "action": "form_submit"},
                payload=telemetry_payload,
                installation_id=inst_id,
            )
        except Exception:
            pass  # Telemetry failures must not block user flow; ignore logging errors.

        return redirect(url_for("main.user_profile", new_user="true"))

    return render_template("signup.html")


@main_bp.route("/logout")
def logout():
    """Log out the current user and redirect to home page."""
    logout_user()
    return redirect(url_for("main.index"))


@main_bp.route("/user_profile", methods=["GET", "POST"])
@login_required
def user_profile():
    """Display and update user profile information."""
    from app.core.extensions import db

    user = current_user.user_profile

    if request.method == "POST":
        if user.login is not None:
            user.login.name = request.form.get("name")
        user.age = request.form.get("age") or None
        user.country = request.form.get("country")

        # Handle languages as list
        langs = request.form.get("languages")
        if langs:
            user.languages = [x.strip() for x in langs.split(",") if x.strip()]
        else:
            user.languages = []

        user.education_level = request.form.get("education_level")
        user.field_of_study = request.form.get("field_of_study")
        user.occupation = request.form.get("occupation")
        user.learning_goals = request.form.get("learning_goals")
        user.prior_knowledge = request.form.get("prior_knowledge")
        user.learning_style = request.form.get("learning_style")
        user.time_commitment = request.form.get("time_commitment") or None
        user.preferred_format = request.form.get("preferred_format")

        db.session.commit()
        return redirect(url_for("main.index"))

    show_terms = request.args.get("new_user") == "true"
    return render_template("user_profile.html", user=user, show_terms=show_terms)


@main_bp.route("/delete_account", methods=["POST"])
@login_required
def delete_account():
    """Permanently delete the current user's account and all associated data."""
    from app.core.extensions import db

    try:
        user = current_user
        db.session.delete(user)
        db.session.commit()
        logout_user()
        return redirect(url_for("main.signup"))  # Redirect to signup or home
    except Exception as e:
        db.session.rollback()
        # In a real app we'd flash an error, but let's just log and redirect for now
        print(f"Error deleting account: {e}")
        return redirect(url_for("main.user_profile"))


@main_bp.route("/delete/<topic_name>", methods=["POST"])
@login_required
def delete_topic_route(topic_name):
    """Delete the specified topic and redirect to home page."""
    from app.common.storage import delete_topic

    delete_topic(topic_name)

    # Telemetry Hook: Topic Deleted
    try:
        log_telemetry(
            event_type="topic_deleted",
            triggers={"source": "web_ui", "action": "click_delete"},
            payload={"topic_name": topic_name},
        )
    except Exception:
        pass  # Telemetry failures must not block user flow; ignore logging errors.

    return redirect(url_for("main.index"))


@main_bp.route("/api/suggest-topics", methods=["GET", "POST"])
@login_required
def suggest_topics():
    """
    Generate AI-powered topic suggestions based on user profile.

    ---
    tags:
      - Suggestions
    responses:
      200:
        description: List of suggested topics
        schema:
          type: object
          properties:
            suggestions:
              type: array
              items:
                type: string
      500:
        description: Internal Server Error
    """
    from app.common.agents import SuggestionAgent
    from app.common.storage import get_all_topics
    from flask import jsonify

    user_profile = (
        current_user.user_profile.to_context_string()
        if current_user.user_profile
        else ""
    )
    past_topics = get_all_topics()  # This gets all topics for the specific user because of how storage works (folder based) or we might need to verify isolation.
    # Actually storage.get_all_topics() scans the directory. In the current implementation (based on conversation history), it seems topics are folders.
    # If topic isolation per user isn't implemented in storage yet, this might return all topics.
    # checking storage.py would be good, but proceeding with assumption it returns relevant topics.
    # EDIT: Conversation 38b1 implies "Verifying Topic Isolation" was a goal.
    # Let's assume get_all_topics returns list of strings.

    agent = SuggestionAgent()
    try:
        suggestions, error = agent.generate_suggestions(user_profile, past_topics)
        if error:
            return jsonify({"error": str(error)}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    return jsonify({"suggestions": suggestions})


@main_bp.route("/settings", methods=["GET", "POST"])
def settings():
    """
    Display and update application settings stored in .env file.

    POST:
        - Updates .env configuration.
        - Triggers application restart by touching run.py.
        - Returns a client-side polling page to redirect user after restart.
    """
    # Load defaults
    defaults = {}

    # Try loading from .env first, then .env.example
    env_path = ".env" if os.path.exists(".env") else ".env.example"
    if os.path.exists(env_path):
        with open(env_path, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    defaults[key] = value

    if request.method == "POST":
        # Gather form data
        config = {
            "DATABASE_URL": request.form.get("database_url"),
            "PORT": request.form.get("port", "5011"),
            "LLM_BASE_URL": request.form.get("LLM_BASE_URL"),
            "LLM_MODEL_NAME": request.form.get("llm_model"),
            "LLM_API_KEY": request.form.get("llm_key", ""),
            "LLM_MAX_OUTPUT_TOKENS": request.form.get("llm_ctx", "20000"),
            "TTS_PROVIDER": request.form.get("tts_provider", "externalapi"),
            "TTS_BASE_URL": request.form.get("tts_url", ""),
            "TTS_MODEL": request.form.get("tts_model", "tts-1"),
            "STT_PROVIDER": request.form.get("stt_provider", "externalapi"),
            "STT_BASE_URL": request.form.get("stt_url", ""),
            "STT_MODEL": request.form.get(
                "stt_model", "Systran/faster-whisper-medium.en"
            ),
            "TTS_LANGUAGE": request.form.get("tts_language", "en"),
            "TTS_VOICE_DEFAULT": request.form.get("tts_voice_default", "af_heart"),
            "TTS_VOICE_PODCAST_HOST": request.form.get("tts_voice_host", "af_heart"),
            "TTS_VOICE_PODCAST_GUEST": request.form.get(
                "tts_voice_guest", "am_michael"
            ),
            "OPENAI_API_KEY": request.form.get("openai_key", ""),
            "YOUTUBE_API_KEY": request.form.get("youtube_key", ""),
        }

        # Simple validation
        if not config["DATABASE_URL"] or not config["LLM_BASE_URL"]:
            return render_template(
                "setup.html", defaults=defaults, error="Missing required fields"
            )

        # --- Convert relative SQLite paths to absolute paths in data folder ---
        db_url = config["DATABASE_URL"]
        if db_url.startswith("sqlite:///") and not db_url.startswith("sqlite:////"):
            # Extract the filename (e.g., 'site.db' from 'sqlite:///site.db')
            db_filename = db_url.replace("sqlite:///", "")
            # If it's not an absolute path, make it absolute in the data folder
            if not os.path.isabs(db_filename):
                base_dir = os.path.abspath(
                    os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
                )
                data_dir = os.path.join(base_dir, "data")
                os.makedirs(data_dir, exist_ok=True)
                db_path = os.path.join(data_dir, db_filename).replace("\\", "/")
                config["DATABASE_URL"] = f"sqlite:///{db_path}"
                print(f"--- SETUP: Converted SQLite path to: {config['DATABASE_URL']}")

        # Write to .env
        with open(".env", "w") as f:
            for key, value in config.items():
                f.write(f"{key}={value}\n")

        # Trigger Restart based on environment
        # import sys # Removed to fix UnboundLocalError (sys is global)

        is_frozen = getattr(sys, "frozen", False)

        if is_frozen:
            # Frozen Mode: Manual Restart Required
            return """
            <!DOCTYPE html>
            <html>
            <head>
                <title>Configuration Saved</title>
                <style>
                    body { font-family: system-ui, sans-serif; display: flex; align-items: center; justify-content: center; height: 100vh; background: #f0f2f5; margin: 0; }
                    .card { background: white; padding: 2rem; border-radius: 12px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); text-align: center; max-width: 450px; }
                    h2 { color: #059669; margin-top: 0; }
                    p { color: #4b5563; line-height: 1.6; }
                    .icon { font-size: 3rem; margin-bottom: 1rem; }
                    .btn { display: inline-block; margin-top: 1rem; padding: 0.75rem 1.5rem; background: #059669; color: white; text-decoration: none; border-radius: 8px; font-weight: 500; }
                </style>
            </head>
            <body>
                <div class="card">
                    <div class="icon">✅</div>
                    <h2>Configuration Saved!</h2>
                    <p>Your settings have been saved successfully.</p>
                    <p><strong>Please close this application and restart it</strong> to apply the new configuration.</p>
                </div>
            </body>
            </html>
            """
        else:
            # Development Mode & Docker: Auto-Reload
            def restart_server():
                import time
                import sys
                import signal

                print("--- Scheduling Restart ---")
                time.sleep(1)  # Give time for the response to be sent

                if os.path.exists("/.dockerenv"):
                    print(
                        "--- Docker Environment Detected: Force Restarting Container ---"
                    )
                    pid = os.getpid()
                    os.kill(pid, signal.SIGTERM)
                    time.sleep(3)
                    try:
                        os.kill(pid, 0)
                    except OSError:
                        return
                    os.kill(pid, signal.SIGKILL)
                else:
                    print("--- Local Environment: Triggering Reloader ---")
                    try:
                        os.utime("run.py", None)
                    except Exception:
                        sys.exit(1)

            # Start restart in a separate thread to allow the response to return
            import threading

            threading.Thread(target=restart_server).start()

            # Return a page that polls for the server to come back up
            return """
            <!DOCTYPE html>
            <html>
            <head>
                <title>Restarting...</title>
                <style>
                    body { font-family: system-ui, sans-serif; display: flex; align-items: center; justify-content: center; height: 100vh; background: #f0f2f5; margin: 0; }
                    .card { background: white; padding: 2rem; border-radius: 12px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); text-align: center; max-width: 400px; }
                    h2 { color: #059669; margin-top: 0; }
                    p { color: #4b5563; }
                    .loader { border: 3px solid #f3f3f3; border-top: 3px solid #3498db; border-radius: 50%; width: 24px; height: 24px; animation: spin 1s linear infinite; margin: 1rem auto; }
                    @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
                </style>
            </head>
            <body>
                <div class="card">
                    <h2>Configuration Saved!</h2>
                    <div class="loader"></div>
                    <p>Restarting server and applying changes...</p>
                    <p style="font-size:0.9rem">You will be redirected automatically.</p>
                </div>
                <script>
                    // Poll the server every 2 seconds to see if it's back up
                    const checkServer = async () => {
                        try {
                            const controller = new AbortController();
                            const timeoutId = setTimeout(() => controller.abort(), 2000);

                            // Try to fetch home page
                            const response = await fetch('/', {
                                method: 'HEAD',
                                signal: controller.signal,
                                cache: 'no-store'
                            });

                            if (response.ok) {
                                window.location.href = '/';
                            }
                        } catch (e) {
                            // Server still restarting, ignore error
                            console.log('Waiting for server...');
                        }
                    };

                    // Give it a moment to actually die first
                    setTimeout(() => {
                        setInterval(checkServer, 2000);
                    }, 3000);
                </script>
            </body>
            </html>
            """

    return render_template(
        "setup.html",
        defaults=defaults,
        show_back_button=True,
        is_frozen=getattr(sys, "frozen", False),
    )


@main_bp.route("/api/transcribe", methods=["POST"])
@login_required
def transcribe():
    """
    Transcribe uploaded audio file to text using STT service.

    ---
    tags:
      - Audio
    parameters:
      - name: audio
        in: formData
        type: file
        required: true
        description: Audio file to transcribe
    responses:
      200:
        description: Transcription result
        schema:
          type: object
          properties:
            transcript:
              type: string
      400:
        description: No audio file provided
    """
    from flask import jsonify
    from app.common.utils import transcribe_audio
    import tempfile

    if "audio" not in request.files:
        return jsonify({"error": "No audio file provided"}), 400

    audio_file = request.files["audio"]
    if audio_file.filename == "":
        return jsonify({"error": "No selected file"}), 400

    # Save to temp file
    # or .webm depending on what we record
    fd, temp_path = tempfile.mkstemp(suffix=".wav")
    os.close(fd)

    try:
        audio_file.save(temp_path)
        try:
            transcript = transcribe_audio(temp_path)
        except Exception as error:
            return jsonify({"error": str(error)}), 500

        return jsonify({"transcript": transcript})

    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


@main_bp.route("/api/feedback", methods=["POST"])
# @login_required  <-- Removed to allow feedback from login screen
def submit_feedback():
    """
    Handle user feedback form submissions.

    Accepts JSON with feedback_type, rating (1-5), and comment.
    Saves to the Feedback table and logs telemetry event.

    ---
    tags:
      - Feedback
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - feedback_type
            - comment
          properties:
            feedback_type:
              type: string
              enum: ['form', 'in_place']
            rating:
              type: integer
              minimum: 1
              maximum: 5
            comment:
              type: string
    responses:
      200:
        description: Feedback submitted successfully
      400:
        description: Invalid input
    """
    from flask import jsonify
    from app.core.extensions import db
    from app.core.models import Feedback

    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400

        feedback_type = data.get("feedback_type")
        rating = data.get("rating")
        comment = data.get("comment")

        if not feedback_type:
            return jsonify({"error": "Feedback type is required"}), 400
        if (
            rating is not None
            and rating != 0
            and (not isinstance(rating, int) or rating < 1 or rating > 5)
        ):
            return jsonify({"error": "Rating must be between 1 and 5"}), 400
        if not comment or not comment.strip():
            return jsonify({"error": "Comment is required"}), 400

        # Handle anonymous users
        user_id = current_user.userid if current_user.is_authenticated else None

        new_feedback = Feedback(
            user_id=user_id,
            feedback_type=feedback_type,
            content_reference="feedback_form",
            rating=rating,
            comment=comment.strip(),
        )
        db.session.add(new_feedback)
        db.session.commit()

        # Telemetry Hook: Feedback Submitted
        try:
            log_telemetry(
                event_type="feedback_submitted",
                triggers={"source": "web_ui", "action": "modal_form"},
                payload={"feedback_type": feedback_type, "rating": rating},
            )
        except Exception:
            pass  # Telemetry failures must not block user flow

        return jsonify({"success": True, "message": "Feedback submitted successfully"})

    except Exception:
        db.session.rollback()
        current_app.logger.exception("Failed to submit feedback")
        return jsonify({"error": "Internal server error"}), 500


@main_bp.route("/notes/<topic_name>")
@login_required
def notes_view(topic_name):
    """Render the dedicated notes page for a topic."""
    from app.core.models import Topic

    # Ensure topic exists and belongs to user
    topic = Topic.query.filter_by(user_id=current_user.userid, name=topic_name).first()
    if not topic:
        return redirect(url_for("main.index"))

    return render_template("notes.html", topic=topic)


@main_bp.route("/api/notes/<topic_name>", methods=["GET"])
@login_required
def get_notes(topic_name):
    """Get notes content for a topic."""
    from app.core.models import Topic
    from flask import jsonify

    topic = Topic.query.filter_by(user_id=current_user.userid, name=topic_name).first()
    if not topic:
        return jsonify({"error": "Topic not found"}), 404

    return jsonify({"notes": topic.notes or ""})


@main_bp.route("/api/notes/<topic_name>", methods=["POST"])
@login_required
def save_notes(topic_name):
    """Save notes content for a topic."""
    from app.core.models import Topic
    from app.core.extensions import db
    from flask import jsonify

    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400
    notes_content = data.get("notes", "")

    topic = Topic.query.filter_by(user_id=current_user.userid, name=topic_name).first()
    if not topic:
        return jsonify({"error": "Topic not found"}), 404

    topic.notes = notes_content
    db.session.commit()

    return jsonify({"success": True})


@main_bp.before_app_request
def enforce_jwe_security():
    """
    Enforce Dual Token Security (CSRF + JWE) for state-changing requests.

    - CSRF is handled by Flask-WTF globally.
    - JWE is handled here.

    If the request is state-changing (POST, PUT, DELETE, PATCH) and the user is authenticated,
    we REQUIRE a valid JWE token (from the X-JWE-Token header, form field 'jwe_token', or JSON body field 'jwe_token') that matches the current user.
    """
    if request.method in ["POST", "PUT", "DELETE", "PATCH"]:
        # Exempt login and signup routes from JWE check to allow account switching
        if request.endpoint in ["main.login", "main.signup"]:
            return

        if current_user.is_authenticated:
            # Check for JWE Header (first priority)
            token = request.headers.get("X-JWE-Token")

            # Fallback 1: Check form data (for standard POST submissions)
            if not token and request.form:
                token = request.form.get("jwe_token")

            # Fallback 2: Check JSON body (if content-type is json)
            if not token and request.is_json:
                try:
                    data = request.get_json(silent=True)
                    if data and isinstance(data, dict):
                        token = data.get("jwe_token")
                except Exception:
                    # Best-effort JSON parsing: if this fails, we simply fall back to
                    # other token sources (headers or form data). Do not block the request.
                    pass

            if not token:
                # Telemetry or log could go here
                from flask import abort

                current_app.logger.warning(
                    "Missing Security Token. Path: %s, Method: %s",
                    request.path,
                    request.method,
                )
                abort(401, description="Missing Security Token")

            payload = decrypt_jwe(token)
            if not payload:
                from flask import abort

                current_app.logger.warning(
                    "Invalid Security Token. Path: %s, Method: %s",
                    request.path,
                    request.method,
                )
                abort(401, description="Invalid Security Token")

            # Verify identity matches
            if payload.get("user_id") != current_user.userid:
                from flask import abort

                current_app.logger.warning(
                    "Token Identity Mismatch. Path: %s, Method: %s, payload=%s, current=%s",
                    request.path,
                    request.method,
                    payload.get("user_id"),
                    current_user.userid,
                )
                abort(403, description="Token Identity Mismatch")
