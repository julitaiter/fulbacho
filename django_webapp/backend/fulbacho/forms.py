from django import forms
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.forms import formset_factory
from django.utils import timezone

from .models import FriendGroup, Match, Player, Team


class EmailOrUsernameAuthenticationForm(AuthenticationForm):
    username = forms.CharField(label="Usuario o email")

    def clean(self):
        username = self.cleaned_data.get("username")
        password = self.cleaned_data.get("password")

        if username and "@" in username:
            User = get_user_model()
            user = User.objects.filter(email__iexact=username).first()
            if user:
                username = user.get_username()
                self.cleaned_data["username"] = username

        if username is not None and password:
            self.user_cache = authenticate(
                self.request,
                username=username,
                password=password,
            )
            if self.user_cache is None:
                raise self.get_invalid_login_error()
            self.confirm_login_allowed(self.user_cache)

        return self.cleaned_data


class RegisterForm(UserCreationForm):
    email = forms.EmailField(label="Email")
    display_name = forms.CharField(label="Nombre visible", required=False)

    class Meta(UserCreationForm.Meta):
        model = get_user_model()
        fields = ("username", "email", "display_name")

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        User = get_user_model()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Ya existe un usuario con ese email.")
        return email


class GroupForm(forms.ModelForm):
    class Meta:
        model = FriendGroup
        fields = ["name"]
        labels = {"name": "Nombre del grupo"}


class JoinGroupForm(forms.Form):
    code = forms.CharField(label="Código del grupo", max_length=6, min_length=6)

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


class PlayerForm(forms.ModelForm):
    class Meta:
        model = Player
        fields = ["name", "linked_user"]
        labels = {
            "name": "Nombre o apodo",
            "linked_user": "Usuario vinculado, opcional",
        }

    def __init__(self, *args, group=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.group = group
        self.fields["linked_user"].required = False
        if group:
            self.fields["linked_user"].queryset = get_user_model().objects.filter(
                group_memberships__group=group
            ).distinct()

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        qs = Player.objects.filter(group=self.group, name__iexact=name)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if self.group and qs.exists():
            raise forms.ValidationError("Ya existe un jugador con ese nombre en el grupo.")
        return name


class MatchForm(forms.ModelForm):
    played_at = forms.DateTimeField(
        label="Fecha y hora",
        input_formats=["%Y-%m-%dT%H:%M"],
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"}),
    )

    class Meta:
        model = Match
        fields = [
            "played_at",
            "modality",
            "location",
            "team_a_name",
            "team_b_name",
            "score_a",
            "score_b",
        ]
        labels = {
            "modality": "Modalidad",
            "location": "Cancha o lugar",
            "team_a_name": "Nombre Equipo A",
            "team_b_name": "Nombre Equipo B",
            "score_a": "Goles Equipo A",
            "score_b": "Goles Equipo B",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk and not self.initial.get("played_at"):
            self.initial["played_at"] = timezone.localtime().strftime("%Y-%m-%dT%H:%M")
        elif self.instance.pk and self.instance.played_at:
            self.initial["played_at"] = timezone.localtime(self.instance.played_at).strftime("%Y-%m-%dT%H:%M")


class MatchRosterForm(forms.Form):
    team_a_players = forms.ModelMultipleChoiceField(
        label="Jugadores Equipo A",
        queryset=Player.objects.none(),
        widget=forms.CheckboxSelectMultiple,
    )
    team_b_players = forms.ModelMultipleChoiceField(
        label="Jugadores Equipo B",
        queryset=Player.objects.none(),
        widget=forms.CheckboxSelectMultiple,
    )

    def __init__(self, *args, player_queryset=None, **kwargs):
        super().__init__(*args, **kwargs)
        player_queryset = player_queryset if player_queryset is not None else Player.objects.none()
        self.fields["team_a_players"].queryset = player_queryset
        self.fields["team_b_players"].queryset = player_queryset

    def clean(self):
        cleaned = super().clean()
        team_a = list(cleaned.get("team_a_players") or [])
        team_b = list(cleaned.get("team_b_players") or [])

        if len(team_a) < 2:
            self.add_error("team_a_players", "Elegí al menos 2 jugadores para el Equipo A.")
        if len(team_b) < 2:
            self.add_error("team_b_players", "Elegí al menos 2 jugadores para el Equipo B.")

        ids_a = {player.id for player in team_a}
        ids_b = {player.id for player in team_b}
        if ids_a.intersection(ids_b):
            raise forms.ValidationError("Un jugador no puede estar en los dos equipos.")

        return cleaned


class GoalLineForm(forms.Form):
    team_scored_for = forms.ChoiceField(
        label="Suma para",
        choices=[("", "Sin gol")] + list(Team.choices),
        required=False,
    )
    player = forms.ModelChoiceField(
        label="Jugador",
        queryset=Player.objects.none(),
        required=False,
        help_text="Puede quedar vacío si el gol no se asigna a nadie.",
    )
    own_goal = forms.BooleanField(label="Gol en contra", required=False)

    def __init__(self, *args, player_queryset=None, **kwargs):
        super().__init__(*args, **kwargs)
        player_queryset = player_queryset if player_queryset is not None else Player.objects.none()
        self.fields["player"].queryset = player_queryset

    def clean(self):
        cleaned = super().clean()
        team = cleaned.get("team_scored_for")
        player = cleaned.get("player")
        own_goal = cleaned.get("own_goal")

        if not team and not player and not own_goal:
            return cleaned

        if not team:
            raise forms.ValidationError("Si cargás una fila de gol, indicá a qué equipo suma.")
        if own_goal and not player:
            raise forms.ValidationError("Un gol en contra necesita jugador.")

        return cleaned


GoalFormSet = formset_factory(GoalLineForm, extra=8, can_delete=True)


def build_goal_formset(*, data=None, player_queryset=None, initial=None, prefix="goals"):
    formset = GoalFormSet(data=data, initial=initial or [], prefix=prefix)
    for form in formset.forms:
        form.fields["player"].queryset = player_queryset if player_queryset is not None else Player.objects.none()
    return formset
