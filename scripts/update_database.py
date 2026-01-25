#!/usr/bin/env python
"""
Update database schema in PostgreSQL for the Personal Guru application.
Handles creating missing tables and adding missing columns/updating column types.
"""
import sys
import os
import logging
from dotenv import load_dotenv
from sqlalchemy import inspect, text

# Output buffer for detailed logs (to prevent spamming stdout if not needed, but here we print)
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

# Add the project root to the python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

load_dotenv()

from app import create_app, db  # noqa: E402
from app.core import models  # noqa: E402

# List of models to check
TARGET_MODELS = [
    models.Topic,
    models.ChapterMode,
    models.QuizMode,
    models.FlashcardMode,
    models.ChatMode,
    models.User,
    models.Installation,
    models.TelemetryLog,
    models.Feedback,
    models.AIModelPerformance,
    models.PlanRevision,
    models.Login
]

def get_column_type(column):
    """
    Returns a string representation of the column type for comparison.
    Simplified for common types used in this app.
    """
    return str(column.type).upper()

def update_database():
    app = create_app()
    with app.app_context():
        logger.info("Starting database update...")

        if db.engine.name == 'sqlite':
            logger.info("Detected SQLite database.")
            # Ensure the database directory exists
            db_uri = app.config['SQLALCHEMY_DATABASE_URI']
            if db_uri.startswith('sqlite:///'):
                db_path = db_uri.replace('sqlite:///', '')
                # Handle relative paths (common in sqlite:///site.db)
                if not os.path.isabs(db_path):
                     db_path = os.path.join(app.instance_path, db_path) # Try instance path layout or current dir?

                     logger.info(f"DEBUG: app.instance_path: {app.instance_path}")
                     logger.info(f"DEBUG: Final DB Path: {os.path.abspath(db_path)}")
                     # Actually default config is sqlite:///site.db, relative to CWD usually or app root.
                     # Let's just create the folder if it implies one.

                # If path contains directories, ensure they exist
                db_dir = os.path.dirname(db_path)
                if db_dir and not os.path.exists(db_dir):
                    logger.info(f"Creating database directory: {db_dir}")
                    os.makedirs(db_dir)

        # 0. Pre-check for table renames (Manual Migrations) - Postgres Only or careful SQLite
        inspector = inspect(db.engine)
        existing_tables = inspector.get_table_names()

        if db.engine.name != 'sqlite':
            if 'study_steps' in existing_tables and 'chapter_mode' not in existing_tables:
                logger.info("Detected legacy table 'study_steps'. Renaming to 'chapter_mode'...")
                try:
                    # Rename table
                    db.session.execute(text('ALTER TABLE study_steps RENAME TO chapter_mode'))
                    db.session.commit()
                    logger.info(" -> Table renamed successfully.")

                    # Check consistency of ID sequence if necessary (usually auto-handled by serial)
                except Exception as e:
                    logger.error(f" -> Failed to rename table: {e}")
                db.session.rollback()

        # 1. Create missing tables (Standard SQLAlchemy)
        logger.info("Ensuring all tables exist...")
        db.create_all()

        # 2. Inspect and Update existing tables
        logger.info("Checking for schema updates...")
        inspector = inspect(db.engine) # Re-inspect after create/rename

        if db.engine.name == 'sqlite':
            logger.info("SQLite mode: Skipping advanced schema inspections (Postgres-specific).")
            return

        for model in TARGET_MODELS:
            table_name = model.__tablename__
            logger.info(f"Inspecting table: {table_name}")

            # Get existing columns in DB
            existing_columns = inspector.get_columns(table_name)
            existing_col_map = {col['name']: col for col in existing_columns}

            # Special check for Topic model migration
            if table_name == 'topics':
                has_user_id = 'user_id' in existing_col_map
                if not has_user_id:
                     logger.warning(" !! Detected old 'topics' table schema (missing user_id). Dropping table to recreate with proper constraints.")
                     # Drop table
                     sql = text('DROP TABLE "topics" CASCADE')
                     db.session.execute(sql)
                     db.session.commit()
                     logger.info("    -> Table dropped. Re-running create_all...")
                     db.create_all()
                     db.create_all()
                     continue # Skip column inspection for this pass

            # Special check for 'chat_history' and 'last_quiz_result' column removal in Topics
            if table_name == 'topics':
                for deprecated_col in ['chat_history', 'last_quiz_result']:
                    if deprecated_col in existing_col_map:
                        logger.info(f"  [-] Dropping deprecated column: {deprecated_col}")
                        try:
                            sql = text(f'ALTER TABLE "topics" DROP COLUMN "{deprecated_col}"')
                            db.session.execute(sql)
                            db.session.commit()
                            logger.info("      -> Dropped successfully.")
                        except Exception as e:
                            logger.error(f"      -> FAILED to drop column: {e}")
                            db.session.rollback()

            # Special check for 'feedback' column removal in ChapterMode (moved to table)
            if table_name == 'chapter_mode':
                 if 'feedback' in existing_col_map:
                      logger.info("  [-] Dropping deprecated column: feedback (moved to Feedback table)")
                      try:
                          sql = text('ALTER TABLE "chapter_mode" DROP COLUMN "feedback"')
                          db.session.execute(sql)
                          db.session.commit()
                          logger.info("      -> Dropped successfully.")
                      except Exception as e:
                          logger.error(f"      -> FAILED to drop column: {e}")
                          db.session.rollback()

            # Special check for renaming 'chat_history' -> 'popup_chat_history' in ChapterMode
            if table_name == 'chapter_mode':
                if 'chat_history' in existing_col_map and 'popup_chat_history' not in existing_col_map:
                    logger.info("  [~] Renaming column 'chat_history' to 'popup_chat_history'")
                    try:
                        sql = text('ALTER TABLE "chapter_mode" RENAME COLUMN "chat_history" TO "popup_chat_history"')
                        db.session.execute(sql)
                        db.session.commit()
                        logger.info("      -> Renamed successfully.")
                        # Update local map
                        existing_col_map['popup_chat_history'] = existing_col_map.pop('chat_history')
                        existing_col_map['popup_chat_history']['name'] = 'popup_chat_history'
                    except Exception as e:
                         logger.error(f"      -> FAILED to rename column: {e}")
                         db.session.rollback()

            # Special check for 'installation_id' removal in Feedback (refactor to user-centric)
            if table_name == 'feedback':
                if 'installation_id' in existing_col_map:
                     logger.info("  [-] Dropping deprecated column: installation_id (moved to User-Centric schema)")
                     try:
                         sql = text('ALTER TABLE "feedback" DROP COLUMN "installation_id"')
                         db.session.execute(sql)
                         db.session.commit()
                         logger.info("      -> Dropped successfully.")
                     except Exception as e:
                         logger.error(f"      -> FAILED to drop column: {e}")
                         db.session.rollback()

            # Usage: TelemetryLog Schema Updates
            if table_name == 'telemetry_logs':
                # 1. Ensure installation_id exists
                if 'installation_id' not in existing_col_map:
                     logger.info("  [+] Adding missing column: installation_id to telemetry_logs")
                     try:
                         # Add as nullable first
                         sql = text('ALTER TABLE "telemetry_logs" ADD COLUMN "installation_id" VARCHAR(36)')
                         db.session.execute(sql)

                         # Backfill attempts from user_id joining logins
                         logger.info("      -> Backfilling installation_id from logins...")
                         sql_backfill = text("""
                            UPDATE telemetry_logs
                            SET installation_id = logins.installation_id
                            FROM logins
                            WHERE telemetry_logs.user_id = logins.userid
                            AND telemetry_logs.installation_id IS NULL
                         """)
                         db.session.execute(sql_backfill)

                         # Delete any rows that still have NULL installation_id (orphans) to allow NOT NULL constraint
                         sql_clean = text('DELETE FROM telemetry_logs WHERE installation_id IS NULL')
                         db.session.execute(sql_clean)

                         # Set NOT NULL
                         sql_const = text('ALTER TABLE "telemetry_logs" ALTER COLUMN "installation_id" SET NOT NULL')
                         db.session.execute(sql_const)

                         # Add FK Constraint
                         sql_fk = text('ALTER TABLE "telemetry_logs" ADD CONSTRAINT fk_telemetry_installation FOREIGN KEY (installation_id) REFERENCES installations(installation_id)')
                         db.session.execute(sql_fk)

                         db.session.commit()
                         logger.info("      -> Added and constrained successfully.")
                     except Exception as e:
                         logger.error(f"      -> FAILED to add column: {e}")
                         db.session.rollback()

                # 2. Ensure user_id is nullable
                if 'user_id' in existing_col_map:
                    # We can't easily check if it's nullable via Inspector in this script style without detailed reflection,
                    # but we can try to ALTER it to DROP NOT NULL blindly or check logic.
                    # For simplicity, we just run the ALTER. Postgres allows this even if already nullable.
                    try:
                        logger.info("  [*] Altering user_id to be NULLABLE")
                        sql = text('ALTER TABLE "telemetry_logs" ALTER COLUMN "user_id" DROP NOT NULL')
                        db.session.execute(sql)
                        db.session.commit()
                    except Exception as e:
                        logger.warning(f"      -> Could not alter user_id: {e}")
                        db.session.rollback()

            # Special check for deprecated 'name' and 'password_hash' columns in User table
            if table_name == 'users':
                for deprecated_col in ['name', 'password_hash']:
                    if deprecated_col in existing_col_map:
                        logger.info(f"  [-] Dropping deprecated column from users: {deprecated_col}")
                        try:
                            sql = text(f'ALTER TABLE "users" DROP COLUMN "{deprecated_col}"')
                            db.session.execute(sql)
                            db.session.commit()
                            logger.info("      -> Dropped successfully.")
                        except Exception as e:
                            logger.error(f"      -> FAILED to drop column: {e}")
                            db.session.rollback()

            # Special check for renaming 'primary_language' -> 'languages' in User table
            if table_name == 'users':
                if 'primary_language' in existing_col_map and 'languages' not in existing_col_map:
                    logger.info("  [~] Renaming column 'primary_language' to 'languages'")
                    try:
                        sql = text('ALTER TABLE "users" RENAME COLUMN "primary_language" TO "languages"')
                        db.session.execute(sql)
                        db.session.commit()
                        logger.info("      -> Renamed successfully.")
                        # Update local map to reflect change for subsequent steps
                        existing_col_map['languages'] = existing_col_map.pop('primary_language')
                        existing_col_map['languages']['name'] = 'languages'
                    except Exception as e:
                         logger.error(f"      -> FAILED to rename column: {e}")
                         db.session.rollback()

            # Special check for renaming 'password' -> 'password_hash' in Login table
            if table_name == 'logins':
                if 'password' in existing_col_map and 'password_hash' not in existing_col_map:
                    logger.info("  [~] Renaming column 'password' to 'password_hash'")
                    try:
                        sql = text('ALTER TABLE "logins" RENAME COLUMN "password" TO "password_hash"')
                        db.session.execute(sql)
                        db.session.commit()
                        logger.info("      -> Renamed successfully.")
                        # Update local map
                        existing_col_map['password_hash'] = existing_col_map.pop('password')
                        existing_col_map['password_hash']['name'] = 'password_hash'
                    except Exception as e:
                         logger.error(f"      -> FAILED to rename column: {e}")
                         db.session.rollback()
            if table_name == 'users':
                 # Special check for User model change (username -> id/login_id)
                 has_username = 'username' in existing_col_map
                 has_id = 'id' in existing_col_map

                 if has_username and not has_id:
                     logger.warning(" !! Detected old 'users' table schema (username PK). Migrating data to new schema...")

                     try:
                         # 1. Backup old data
                         logger.info("    -> Backing up old user data...")
                         old_users_result = db.session.execute(text('SELECT * FROM "users"'))
                         try:
                             # SQLAlchemy 1.4+
                             users_data = [dict(row._mapping) for row in old_users_result]
                         except AttributeError:
                             # Fallback
                             columns = old_users_result.keys()
                             users_data = [dict(zip(columns, row)) for row in old_users_result]

                         logger.info(f"    -> Found {len(users_data)} user(s) to migrate.")

                         # 2. Drop old table
                         sql = text('DROP TABLE "users" CASCADE')
                         db.session.execute(sql)
                         db.session.commit()
                         logger.info("    -> Old 'users' table dropped.")

                         # 3. Recreate tables (User, Login, etc.)
                         logger.info("    -> Re-creating tables...")
                         db.create_all()

                         # 4. Migrate data
                         if users_data:
                             logger.info("    -> Migrating data to new Login/User tables...")
                             migrated_count = 0
                             for u in users_data:
                                 try:
                                     # Generate new UUID for Login
                                     new_userid = models.Login.generate_userid()
                                     old_username = u.get('username')

                                     # Create Login (Auth)
                                     new_login = models.Login(
                                         userid=new_userid,
                                         username=old_username,
                                         name=u.get('name'),
                                         # Map hash to password
                                         password_hash=u.get('password_hash')
                                     )

                                     # Create User (Profile)
                                     langs = u.get('primary_language')
                                     if langs and isinstance(langs, str):
                                         langs = [langs] # Convert to list for JSON
                                     elif not langs:
                                         langs = []

                                     new_user = models.User(
                                        login_id=new_userid,
                                        age=u.get('age'),
                                        country=u.get('country'),
                                        languages=langs,
                                        education_level=u.get('education_level'),
                                        field_of_study=u.get('field_of_study'),
                                        occupation=u.get('occupation'),
                                        learning_goals=u.get('learning_goals'),
                                        prior_knowledge=u.get('prior_knowledge'),
                                        learning_style=u.get('learning_style'),
                                        time_commitment=u.get('time_commitment'),
                                        preferred_format=u.get('preferred_format')
                                     )

                                     db.session.add(new_login)
                                     db.session.add(new_user)

                                     # Update Topic links (restore ownership)
                                     if old_username:
                                         update_topics_sql = text('UPDATE topics SET user_id = :new_uid WHERE user_id = :old_uid')
                                         db.session.execute(update_topics_sql, {'new_uid': new_userid, 'old_uid': old_username})

                                     migrated_count += 1
                                 except Exception as migration_err:
                                     logger.error(f"    -> Error migrating user {u.get('username')}: {migration_err}")

                             db.session.commit()
                             logger.info(f"    -> Migration complete. {migrated_count} users migrated.")

                             # Attempt to restore FK constraint on topics if possible
                             try:
                                 # Best-effort restoration of FK
                                 fk_sql = text('ALTER TABLE topics ADD CONSTRAINT fk_topics_logins FOREIGN KEY (user_id) REFERENCES logins(userid)')
                                 db.session.execute(fk_sql)
                                 db.session.commit()
                                 logger.info("    -> Restored FK constraint on topics table.")
                             except Exception as fk_err:
                                  logger.warning(f"    -> Could not add FK constraint to topics (non-critical): {fk_err}")
                                  db.session.rollback()

                     except Exception as e:
                         logger.error(f"    -> FATAL: Failed to migrate user data: {e}")
                         db.session.rollback()
                         db.create_all()

                     continue
            # Get model columns
            model_columns = model.__table__.columns

            for column in model_columns:
                col_name = column.name
                col_type = column.type



                # Check if column exists
                if col_name not in existing_col_map:
                    logger.info(f"  [+] Adding missing column: {col_name} ({col_type})")
                    # Construct ALTER TABLE statement
                    # Note: This is basic. Default values and nullability might need more complex handling.
                    # For now, we add the column. If not nullable without default, Postgres will complain if table not empty.
                    # We assume nullable or we let it fail if strict.
                    try:
                        # Compile type to SQL string
                        type_str = col_type.compile(dialect=db.engine.dialect)
                        sql = text(f'ALTER TABLE "{table_name}" ADD COLUMN "{col_name}" {type_str}')
                        db.session.execute(sql)
                        db.session.commit()
                        logger.info("      -> Added successfully.")
                    except Exception as e:
                        logger.error(f"      -> FAILED to add column: {e}")
                        db.session.rollback()

                else:
                    # Column exists, check for specific type updates requested (JSONB -> JSON)
                    existing_col_info = existing_col_map[col_name]
                    existing_type_str = str(existing_col_info['type']).upper()
                    model_type_str = str(col_type).upper()

                    # Specific check for JSONB -> JSON
                    # Postgres generic JSON is often represented as 'JSON'
                    # Postgres JSONB is 'JSONB'

                    if 'JSON' in model_type_str and 'JSONB' in existing_type_str:
                         logger.info(f"  [~] Converting column {col_name} from JSONB to JSON")
                         try:
                             # Cast using ::json
                             sql = text(f'ALTER TABLE "{table_name}" ALTER COLUMN "{col_name}" TYPE JSON USING "{col_name}"::json')
                             db.session.execute(sql)
                             db.session.commit()
                             logger.info("      -> Converted successfully.")
                         except Exception as e:
                             logger.error(f"      -> FAILED to convert column: {e}")
                             db.session.rollback()


                    # Special check for languages string -> json
                    if col_name == 'languages' and 'VARCHAR' in existing_type_str and 'JSON' in model_type_str:
                         logger.info(f"  [~] Converting column {col_name} from String to JSON")
                         try:
                             # Convert string "English" to JSON list ["English"]
                             # Postgres specific: using json_build_array or manual formatting
                             # Fallback logic: if empty, '[]', else '["' + val + '"]'
                             # Note: SQL injection risk minimal here as we use columns but content might need escaping if raw string concat.
                             # Safer: USING json_build_array(languages)
                             sql = text(f'ALTER TABLE "{table_name}" ALTER COLUMN "{col_name}" TYPE JSON USING json_build_array("{col_name}")')
                             db.session.execute(sql)
                             db.session.commit()
                             logger.info("      -> Converted successfully.")
                         except Exception as e:
                             logger.error(f"      -> FAILED to convert column: {e}")
                             db.session.rollback()

                    # Special check for VARCHAR(36) -> VARCHAR(100) expansion (for userid)
                    if 'VARCHAR(36)' in existing_type_str and 'VARCHAR(100)' in model_type_str:
                         logger.info(f"  [~] Expanding column {col_name} from VARCHAR(36) to VARCHAR(100)")
                         try:
                             sql = text(f'ALTER TABLE "{table_name}" ALTER COLUMN "{col_name}" TYPE VARCHAR(100)')
                             db.session.execute(sql)
                             db.session.commit()
                             logger.info("      -> Expanded successfully.")
                         except Exception as e:
                             logger.error(f"      -> FAILED to expand column: {e}")
                             db.session.rollback()

        logger.info("✓ Database update complete!")

if __name__ == '__main__':
    update_database()
