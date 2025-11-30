from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from datetime import datetime
from werkzeug.utils import secure_filename
import os

social_bp = Blueprint("social", __name__)

# Configure upload folder
UPLOAD_FOLDER = 'app/static/uploads/posts'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# =====================================================================
# YOUR PAGE - Posts and Comments
# =====================================================================

@social_bp.route("/your-page")
def your_page():
    """View all posts with comments and likes"""
    if "user_id" not in session:
        flash("Please log in to view posts", "danger")
        return redirect(url_for("auth.login"))
    
    from app.models import Post, User
    
    user = User.query.get(session["user_id"])
    posts = Post.query.order_by(Post.created_at.desc()).all()
    
    return render_template("your_page.html", posts=posts, user=user)


@social_bp.route("/post/create", methods=["GET", "POST"])
def create_post():
    """Create a new post with optional file upload"""
    if "user_id" not in session:
        flash("Please log in to create a post", "danger")
        return redirect(url_for("auth.login"))
    
    if request.method == "POST":
        from app.models import Post
        
        content = request.form.get("content")
        image_url = None
        
        if not content or len(content.strip()) == 0:
            flash("Post content cannot be empty", "danger")
            return redirect(url_for("social.create_post"))
        
        if len(content) > 5000:
            flash("Post content is too long (max 5000 characters)", "danger")
            return redirect(url_for("social.create_post"))
        
        # Handle file upload
        if 'photo' in request.files:
            file = request.files['photo']
            if file and file.filename and allowed_file(file.filename):
                try:
                    filename = secure_filename(f"{session['user_id']}_{datetime.now().timestamp()}_{file.filename}")
                    
                    # Create upload directory if it doesn't exist
                    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
                    
                    filepath = os.path.join(UPLOAD_FOLDER, filename)
                    file.save(filepath)
                    
                    # Store relative path for URL
                    image_url = f"/static/uploads/posts/{filename}"
                except Exception as e:
                    flash(f"Error uploading file: {str(e)}", "danger")
                    return redirect(url_for("social.create_post"))
            elif file.filename:
                flash("Invalid file format. Allowed: JPG, PNG, GIF, WebP", "danger")
                return redirect(url_for("social.create_post"))
        
        post = Post.create(
            user_id=session["user_id"],
            content=content,
            image_url=image_url
        )
        
        flash("Post created successfully!", "success")
        return redirect(url_for("social.your_page"))
    
    return render_template("create_post.html")


@social_bp.route("/post/<int:post_id>/edit", methods=["GET", "POST"])
def edit_post(post_id):
    """Edit a post with optional file upload"""
    from app.models import Post
    
    post = Post.query.get_or_404(post_id)
    
    if post.user_id != session.get("user_id"):
        flash("You can only edit your own posts", "danger")
        return redirect(url_for("social.your_page"))
    
    if request.method == "POST":
        content = request.form.get("content")
        remove_image = request.form.get("remove_image", "0")
        
        if not content or len(content.strip()) == 0:
            flash("Post content cannot be empty", "danger")
            return redirect(url_for("social.edit_post", post_id=post_id))
        
        if len(content) > 5000:
            flash("Post content is too long (max 5000 characters)", "danger")
            return redirect(url_for("social.edit_post", post_id=post_id))
        
        image_url = post.image_url
        
        # Handle image removal
        if remove_image == "1":
            if post.image_url:
                try:
                    image_path = os.path.join('app', post.image_url.lstrip('/'))
                    if os.path.exists(image_path):
                        os.remove(image_path)
                except Exception as e:
                    print(f"Error deleting old image: {e}")
            image_url = None
        
        # Handle new file upload
        if 'photo' in request.files:
            file = request.files['photo']
            if file and file.filename and allowed_file(file.filename):
                try:
                    # Delete old image if exists
                    if post.image_url:
                        try:
                            old_path = os.path.join('app', post.image_url.lstrip('/'))
                            if os.path.exists(old_path):
                                os.remove(old_path)
                        except Exception as e:
                            print(f"Error deleting old image: {e}")
                    
                    filename = secure_filename(f"{session['user_id']}_{datetime.now().timestamp()}_{file.filename}")
                    
                    # Create upload directory if it doesn't exist
                    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
                    
                    filepath = os.path.join(UPLOAD_FOLDER, filename)
                    file.save(filepath)
                    
                    # Store relative path for URL
                    image_url = f"/static/uploads/posts/{filename}"
                except Exception as e:
                    flash(f"Error uploading file: {str(e)}", "danger")
                    return redirect(url_for("social.edit_post", post_id=post_id))
            elif file.filename:
                flash("Invalid file format. Allowed: JPG, PNG, GIF, WebP", "danger")
                return redirect(url_for("social.edit_post", post_id=post_id))
        
        post.update_content(content)
        post.image_url = image_url
        from app import db
        db.session.commit()
        
        flash("Post updated successfully!", "success")
        return redirect(url_for("social.your_page"))
    
    return render_template("edit_post.html", post=post)


@social_bp.route("/post/<int:post_id>/delete", methods=["POST"])
def delete_post(post_id):
    """Delete a post"""
    from app.models import Post
    
    post = Post.query.get_or_404(post_id)
    
    if post.user_id != session.get("user_id"):
        flash("You can only delete your own posts", "danger")
        return redirect(url_for("social.your_page"))
    
    post.delete()
    flash("Post deleted successfully!", "success")
    return redirect(url_for("social.your_page"))


@social_bp.route("/post/<int:post_id>/like", methods=["POST"])
def toggle_like(post_id):
    """Toggle like on a post"""
    if "user_id" not in session:
        return jsonify({"error": "Not logged in"}), 401
    
    from app.models import Post, User
    
    post = Post.query.get_or_404(post_id)
    user = User.query.get(session["user_id"])
    
    is_liked = post.toggle_like(user)
    like_count = post.get_like_count()
    
    return jsonify({
        "status": "success",
        "is_liked": is_liked,
        "like_count": like_count
    })


@social_bp.route("/post/<int:post_id>/comment", methods=["POST"])
def add_comment(post_id):
    """Add a comment to a post"""
    if "user_id" not in session:
        flash("Please log in to comment", "danger")
        return redirect(url_for("auth.login"))
    
    from app.models import Post, Comment
    
    post = Post.query.get_or_404(post_id)
    content = request.form.get("comment_content")
    
    if not content or len(content.strip()) == 0:
        flash("Comment cannot be empty", "danger")
        return redirect(url_for("social.your_page"))
    
    if len(content) > 1000:
        flash("Comment is too long (max 1000 characters)", "danger")
        return redirect(url_for("social.your_page"))
    
    Comment.create(
        post_id=post_id,
        user_id=session["user_id"],
        content=content
    )
    
    flash("Comment added successfully!", "success")
    return redirect(url_for("social.your_page"))


@social_bp.route("/comment/<int:comment_id>/edit", methods=["POST"])
def edit_comment(comment_id):
    """Edit a comment"""
    from app.models import Comment
    
    comment = Comment.query.get_or_404(comment_id)
    
    if comment.user_id != session.get("user_id"):
        flash("You can only edit your own comments", "danger")
        return redirect(url_for("social.your_page"))
    
    content = request.form.get("comment_content")
    
    if not content or len(content.strip()) == 0:
        flash("Comment cannot be empty", "danger")
        return redirect(url_for("social.your_page"))
    
    if len(content) > 1000:
        flash("Comment is too long (max 1000 characters)", "danger")
        return redirect(url_for("social.your_page"))
    
    comment.update(content)
    flash("Comment updated successfully!", "success")
    return redirect(url_for("social.your_page"))


@social_bp.route("/comment/<int:comment_id>/delete", methods=["POST"])
def delete_comment(comment_id):
    """Delete a comment"""
    from app.models import Comment
    
    comment = Comment.query.get_or_404(comment_id)
    post_id = comment.post_id
    
    if comment.user_id != session.get("user_id"):
        flash("You can only delete your own comments", "danger")
        return redirect(url_for("social.your_page"))
    
    comment.delete()
    flash("Comment deleted successfully!", "success")
    return redirect(url_for("social.your_page"))


# =====================================================================
# GAMIFICATION - Badges and XP
# =====================================================================

@social_bp.route("/gamification")
def gamification():
    """View gamification dashboard with badges and XP"""
    if "user_id" not in session:
        flash("Please log in to view gamification", "danger")
        return redirect(url_for("auth.login"))
    
    from app.models import User, Badge
    
    user = User.query.get(session["user_id"])
    user_stats = user.ensure_stats()
    
    # Get all badges for this user
    badges = Badge.query.filter_by(user_stats_id=user_stats.id).all()
    
    # Calculate level and progress
    level = user_stats.get_level()
    level_progress = user_stats.get_level_progress()
    
    # Calculate XP needed for next level
    current_xp = user_stats.total_xp
    current_level_xp = level * 50
    next_level_xp = (level + 1) * 50
    xp_for_next_level = next_level_xp - current_xp
    
    return render_template(
        "gamification.html",
        user_stats=user_stats,
        badges=badges,
        level=level,
        level_progress=level_progress,
        xp_for_next_level=xp_for_next_level
    )


@social_bp.route("/api/user-stats")
def get_user_stats():
    """API endpoint to get user stats"""
    if "user_id" not in session:
        return jsonify({"error": "Not logged in"}), 401
    
    from app.models import User, Badge
    
    user = User.query.get(session["user_id"])
    user_stats = user.ensure_stats()
    
    badges = Badge.query.filter_by(user_stats_id=user_stats.id).all()
    
    return jsonify({
        "username": user.username,
        "total_xp": user_stats.total_xp,
        "tasks_completed": user_stats.tasks_completed,
        "level": user_stats.get_level(),
        "level_progress": user_stats.get_level_progress(),
        "badges": [
            {
                "name": b.name,
                "icon": b.icon,
                "description": b.description,
                "earned_at": b.earned_at.strftime("%Y-%m-%d %H:%M")
            }
            for b in badges
        ]
    })


@social_bp.route("/leaderboard")
def leaderboard():
    """View global leaderboard"""
    if "user_id" not in session:
        flash("Please log in to view leaderboard", "danger")
        return redirect(url_for("auth.login"))
    
    from app.models import UserStats
    
    # Get top users by XP
    top_users = UserStats.query.order_by(UserStats.total_xp.desc()).limit(50).all()
    
    return render_template("leaderboard.html", top_users=top_users)


# Add these routes to your social.py file

@social_bp.route("/explore")
def explore():
    """Explore all hashtags and popular posts"""
    if "user_id" not in session:
        flash("Please log in to explore", "danger")
        return redirect(url_for("auth.login"))
    
    from app.models import Post
    import re
    
    # Get all posts
    all_posts = Post.query.order_by(Post.created_at.desc()).all()
    
    # Extract hashtags from all posts
    hashtags_dict = {}
    for post in all_posts:
        # Find all hashtags in post content
        tags = re.findall(r'#\w+', post.content)
        for tag in tags:
            tag_lower = tag.lower()
            if tag_lower not in hashtags_dict:
                hashtags_dict[tag_lower] = {'count': 0, 'tag': tag}
            hashtags_dict[tag_lower]['count'] += 1
    
    # Sort by count (most popular first)
    sorted_hashtags = sorted(hashtags_dict.values(), key=lambda x: x['count'], reverse=True)[:20]
    
    # Get recent posts for explore
    recent_posts = all_posts[:10]
    
    return render_template("explore.html", hashtags=sorted_hashtags, recent_posts=recent_posts)


@social_bp.route("/search/hashtag/<tag>")
def search_hashtag(tag):
    """Search posts by hashtag"""
    if "user_id" not in session:
        flash("Please log in to search", "danger")
        return redirect(url_for("auth.login"))
    
    from app.models import Post, User
    import re
    
    # Ensure tag starts with #
    if not tag.startswith('#'):
        tag = '#' + tag
    
    tag_lower = tag.lower()
    
    # Get all posts and filter by hashtag
    all_posts = Post.query.order_by(Post.created_at.desc()).all()
    matching_posts = []
    
    for post in all_posts:
        if tag_lower in post.content.lower():
            matching_posts.append(post)
    
    user = User.query.get(session["user_id"])
    
    return render_template("hashtag_results.html", hashtag=tag, posts=matching_posts, user=user)


@social_bp.route("/search")
def search_posts():
    """Search posts by keyword"""
    if "user_id" not in session:
        flash("Please log in to search", "danger")
        return redirect(url_for("auth.login"))
    
    from app.models import Post, User
    
    query = request.args.get('q', '').strip()
    
    if not query:
        flash("Please enter a search term", "warning")
        return redirect(url_for("social.explore"))
    
    # Search in post content
    all_posts = Post.query.order_by(Post.created_at.desc()).all()
    matching_posts = [p for p in all_posts if query.lower() in p.content.lower()]
    
    user = User.query.get(session["user_id"])
    
    return render_template("search_result.html", query=query, posts=matching_posts, user=user)