from django import forms
from django.utils import timezone


class LoginForm(forms.Form):
    email = forms.EmailField(label="Email")
    password = forms.CharField(label="Contraseña", widget=forms.PasswordInput)


class RegisterForm(forms.Form):
    display_name = forms.CharField(label="Nombre visible", max_length=100)
    email = forms.EmailField(label="Email")
    password = forms.CharField(label="Contraseña", min_length=8, max_length=128, widget=forms.PasswordInput)
    password_confirm = forms.CharField(label="Repetir contraseña", min_length=8, max_length=128, widget=forms.PasswordInput)

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("password") and cleaned.get("password_confirm") and cleaned["password"] != cleaned["password_confirm"]:
            self.add_error("password_confirm", "Las contraseñas no coinciden.")
        return cleaned


class GroupForm(forms.Form):
    name = forms.CharField(label="Nombre del grupo", max_length=100)


class JoinGroupForm(forms.Form):
    code = forms.CharField(label="Código del grupo", min_length=6, max_length=6)

    def clean_code(self):
        return self.cleaned_data["code"].strip().upper()


class GuestCodeForm(JoinGroupForm):
    pass


class CsvImportForm(forms.Form):
    file = forms.FileField(label="Archivo CSV")

    def clean_file(self):
        uploaded_file = self.cleaned_data["file"]
        if not uploaded_file.name.lower().endswith(".csv"):
            raise forms.ValidationError("Subí un archivo con extensión .csv.")
        return uploaded_file


class PlayerForm(forms.Form):
    name = forms.CharField(label="Nombre o apodo", max_length=100)
    linked_user_id = forms.ChoiceField(label="Usuario vinculado, opcional", required=False)

    def __init__(self, *args, members=None, current_linked_user_id=None, **kwargs):
        super().__init__(*args, **kwargs)
        members = members or []
        choices = [("", "Sin usuario vinculado")]
        for member in members:
            label = member.get("display_name") or member.get("email")
            choices.append((str(member["user_id"]), f"{label} ({member['email']})"))
        self.fields["linked_user_id"].choices = choices
        if current_linked_user_id and not self.is_bound:
            self.initial["linked_user_id"] = str(current_linked_user_id)


class MatchForm(forms.Form):
    played_at = forms.DateTimeField(
        label="Fecha y hora",
        input_formats=["%Y-%m-%dT%H:%M"],
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"}),
    )
    players_per_team = forms.IntegerField(label="Formato (jugadores por equipo)", min_value=1, max_value=50, initial=5)
    location = forms.CharField(label="Cancha o lugar", max_length=200, required=False)
    team_a_name = forms.CharField(label="Nombre Equipo A", max_length=100, initial="Equipo A")
    team_b_name = forms.CharField(label="Nombre Equipo B", max_length=100, initial="Equipo B")
    score_a = forms.IntegerField(label="Goles Equipo A", min_value=0, initial=0)
    score_b = forms.IntegerField(label="Goles Equipo B", min_value=0, initial=0)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.is_bound and not self.initial.get("played_at"):
            self.initial["played_at"] = timezone.localtime().strftime("%Y-%m-%dT%H:%M")


class PromoteCasualForm(forms.Form):
    name = forms.CharField(label="Nombre del nuevo jugador", max_length=100)
    participant_ids = forms.MultipleChoiceField(label="Participaciones a vincular", widget=forms.CheckboxSelectMultiple)
    linked_user_id = forms.ChoiceField(label="Usuario vinculado, opcional", required=False)

    def __init__(self, *args, casuals=None, members=None, **kwargs):
        super().__init__(*args, **kwargs)
        casuals = casuals or []
        members = members or []
        self.fields["participant_ids"].choices = [
            (
                str(item["id"]),
                f"{item['display_name']} · {item['match_played_at'].strftime('%d/%m/%Y') if hasattr(item['match_played_at'], 'strftime') else str(item['match_played_at'])[:10]} · Equipo {item['team']}",
            )
            for item in casuals
        ]
        self.fields["linked_user_id"].choices = [("", "Sin usuario vinculado")] + [
            (
                str(member["user_id"]),
                f"{member.get('display_name') or member.get('email')} ({member['email']})",
            )
            for member in members
        ]


class AttachCasualForm(forms.Form):
    player_id = forms.ChoiceField(label="Jugador habitual")
    participant_ids = forms.MultipleChoiceField(label="Participaciones a vincular", widget=forms.CheckboxSelectMultiple)

    def __init__(self, *args, casuals=None, players=None, **kwargs):
        super().__init__(*args, **kwargs)
        casuals = casuals or []
        players = players or []
        self.fields["player_id"].choices = [(str(item["id"]), item["name"]) for item in players if item.get("active")]
        self.fields["participant_ids"].choices = [
            (
                str(item["id"]),
                f"{item['display_name']} · {item['match_played_at'].strftime('%d/%m/%Y') if hasattr(item['match_played_at'], 'strftime') else str(item['match_played_at'])[:10]} · Equipo {item['team']}",
            )
            for item in casuals
        ]


class MemberRoleForm(forms.Form):
    role = forms.ChoiceField(label="Rol", choices=[("member", "Miembro"), ("admin", "Admin")])
