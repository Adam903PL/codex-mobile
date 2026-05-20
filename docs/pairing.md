# Parowanie telefonu z komputerem

Parowanie laczy konto uzytkownika z konkretnym komputerem. Telefon nie laczy sie bezposrednio z komputerem; oba klienty komunikuja sie z backendem.

## Przeplyw

1. Uzytkownik loguje sie w aplikacji mobilnej.
2. Mobile wysyla `POST /api/pairing-codes/`.
3. Backend zwraca jednorazowy kod, np. `AB12CD`, wazny 10 minut.
4. Wygenerowanie nowego kodu uniewaznia poprzedni aktywny kod tego samego uzytkownika.
5. Uzytkownik uruchamia lokalnie:

```bash
devlink pair --code AB12CD --name "Laptop" --project C:\path\to\repo
```

6. CLI wysyla kod, nazwe komputera, platforme i opcjonalny projekt do backendu.
7. Backend transakcyjnie blokuje kod parowania, sprawdza czy jest wazny i nieuzyty, tworzy `Device` oraz opcjonalny `Project`.
8. Backend zwraca token urzadzenia tylko raz, w odpowiedzi na parowanie.
9. CLI zapisuje token lokalnie w keychainie, a jezeli keychain nie dziala, w fallbacku developerskim.
10. Od tego momentu CLI uzywa naglowka `Authorization: Device <device_token>`.

## Odlaczanie komputera

Mobile odpina komputer przez:

```http
DELETE /api/devices/{id}/
```

Backend nie usuwa rekordu z bazy. Ustawia `Device.status = revoked`, dzieki czemu:

- historia urzadzenia zostaje w bazie,
- projekty nadal sa powiazane z dawnym urzadzeniem,
- kazdy kolejny request CLI z tym tokenem dostaje blad 401/403,
- heartbeat nie moze przywrocic urzadzenia do statusu `online`.

CLI po odrzuceniu tokenu konczy `devlink connect` z komunikatem, ze komputer mogl zostac odlaczony w aplikacji mobilnej.

## Zasady bezpieczenstwa

- Kod parowania jest jednorazowy.
- Kod parowania wygasa po 10 minutach.
- Aktywny moze byc tylko najnowszy niewykorzystany kod uzytkownika.
- Token urzadzenia jest inny niz JWT uzytkownika.
- Backend zapisuje tylko hash tokenu urzadzenia.
- Telefon nie moze wyslac dowolnej sciezki projektu podczas tworzenia taska; wybiera tylko projekty zarejestrowane lokalnie przez CLI.
