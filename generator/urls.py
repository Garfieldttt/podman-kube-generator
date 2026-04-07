from django.urls import path
from django.contrib.auth import views as auth_views
from .forms import AppPasswordResetForm
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('generate/', views.generate_view, name='generate'),
    path('add-container/', views.add_container, name='add_container'),
    path('add-init-container/', views.add_init_container, name='add_init_container'),
    path('image-search/', views.image_search, name='image_search'),
    path('image-preset/', views.image_preset, name='image_preset'),
    path('stack-load/', views.stack_load, name='stack_load'),
    path('connection-hints/', views.connection_hints, name='connection_hints'),
    path('image-tags/', views.image_tags, name='image_tags'),
    path('save/', views.save_config, name='save_config'),
    path('impressum/', views.impressum, name='impressum'),
    path('datenschutz/', views.datenschutz, name='datenschutz'),
    path('stack/<slug:key>/', views.stack_detail, name='stack_detail'),
    path('<uuid:uuid>/', views.saved_detail, name='saved_detail'),
    path('<uuid:uuid>/edit/', views.edit_config, name='edit_config'),
    path('<uuid:uuid>/download/', views.download, name='download'),
    path('<uuid:uuid>/quadlet/', views.download_quadlet, name='download_quadlet'),
    path('<uuid:uuid>/env/', views.download_env, name='download_env'),
    path('<uuid:uuid>/versions/', views.config_versions, name='config_versions'),
    path('<uuid:uuid>/update/', views.update_config, name='update_config'),
    # Auth
    path('register/', views.register, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('activate/<str:uidb64>/<str:token>/', views.activate, name='activate'),
    # Password Reset
    path('password-reset/', auth_views.PasswordResetView.as_view(
        template_name='generator/password_reset.html',
        form_class=AppPasswordResetForm,
        success_url='/password-reset/sent/',
    ), name='password_reset'),
    path('password-reset/sent/', auth_views.PasswordResetDoneView.as_view(
        template_name='generator/password_reset_sent.html',
    ), name='password_reset_done'),
    path('password-reset/confirm/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(
        template_name='generator/password_reset_confirm.html',
        success_url='/password-reset/complete/',
    ), name='password_reset_confirm'),
    path('password-reset/complete/', auth_views.PasswordResetCompleteView.as_view(
        template_name='generator/password_reset_complete.html',
    ), name='password_reset_complete'),
    # Community
    path('my-stacks/', views.my_stacks, name='my_stacks'),
    path('submit-stack/', views.submit_stack, name='submit_stack'),
    path('delete-stack/<int:stack_id>/', views.delete_user_stack, name='delete_user_stack'),
    path('view-stack/<int:stack_id>/', views.view_user_stack, name='view_user_stack'),
    path('edit-stack/<int:stack_id>/', views.edit_user_stack, name='edit_user_stack'),
    path('update-stack/<int:stack_id>/', views.update_user_stack, name='update_user_stack'),
    path('community-stack/', views.community_stack_load, name='community_stack_load'),
    path('check-duplicate/', views.check_duplicate, name='check_duplicate'),
    # Profile
    path('profile/', views.profile_edit, name='profile_edit'),
    path('delete-account/', views.delete_account, name='delete_account'),
    path('u/<str:username>/', views.profile_public, name='profile_public'),
    path('community/', views.community, name='community'),
    path('community/<int:stack_id>/', views.community_stack_detail, name='community_stack_detail'),
    path('community/<int:stack_id>/like/', views.stack_like, name='stack_like'),
    path('community/<int:stack_id>/comment/', views.stack_comment, name='stack_comment'),
    path('avatar-upload/', views.avatar_upload, name='avatar_upload'),
    # Collections
    path('collections/', views.collections_list, name='collections_list'),
    path('collections/new/', views.collection_create, name='collection_create'),
    path('collections/<int:collection_id>/', views.collection_detail, name='collection_detail'),
    path('collections/<int:collection_id>/delete/', views.collection_delete, name='collection_delete'),
    path('collections/<int:collection_id>/remove/<int:item_id>/', views.collection_remove_item, name='collection_remove_item'),
    path('<uuid:uuid>/add-to-collection/', views.config_add_to_collection, name='config_add_to_collection'),
    # Visual Pod Builder
    path('builder/', views.builder_view, name='builder'),
    path('builder/generate/', views.builder_generate, name='builder_generate'),
    path('builder/compose-import/', views.compose_import, name='builder_compose_import'),
    path('builder/image-inspect/', views.image_inspect, name='image_inspect'),
]
