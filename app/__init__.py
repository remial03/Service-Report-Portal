import os
from datetime import timedelta
from flask import Flask
from dotenv import load_dotenv
from werkzeug.middleware.proxy_fix import ProxyFix
from .extensions import login_manager, oauth


def create_app():
    load_dotenv()

    app = Flask(
        __name__,
        static_folder=os.path.join(os.path.dirname(__file__), "..", "static"),
        template_folder=os.path.join(os.path.dirname(__file__), "templates"),
    )
    app.secret_key = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)
    app.config["REMEMBER_COOKIE_DURATION"] = timedelta(days=30)
    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=30)

    if app.secret_key == "dev-secret-key-change-in-production":
        print("WARNING: No SECRET_KEY env var set. Using insecure default.")

    # Init extensions
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    oauth.init_app(app)

    # Register OAuth providers
    from .oauth_providers import register_providers
    register_providers(oauth)

    # Register blueprints
    from .blueprints.auth import auth_bp
    from .blueprints.main import main_bp
    from .blueprints.api import api_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp)

    # Error handlers
    from flask import render_template

    @app.errorhandler(404)
    def not_found(error):
        return render_template("error.html", message="Page not found"), 404

    @app.errorhandler(500)
    def internal_error(error):
        return render_template("error.html", message="Internal server error"), 500

    @app.errorhandler(403)
    def forbidden(error):
        return render_template("error.html", message="Access forbidden"), 403

    return app
