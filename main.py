from flask import Flask, request, jsonify
from datetime import datetime
import pyxirr

app = Flask(__name__)

@app.route("/", methods=["GET"])
def home():
    return "Bienvenue sur l'API MWR Calculator. Utilisez /api/calculate pour soumettre des données.", 200

@app.route('/api/calculate', methods=['POST'])
def calculate_mwr():
    data = request.get_json()

    if not data or "dataset" not in data:
        return jsonify({"error": "Invalid input. Please provide a valid dataset."}), 400

    dataset = data["dataset"]

    # Initialisation des variables
    table = []
    cash_flows = []
    dates = []
    invalid_entries = []  # Collecte des erreurs de validation

    try:
        # Extraire la valeur initiale
        initial_value = dataset[0].get("User base_value_1D", 0)
        if not initial_value:
            return jsonify({"error": "Initial value 'User base_value_1D' is missing."}), 400

        # Ajouter la première ligne
        current_equity = initial_value
        first_date = dataset[0].get("Date")

        # Vérifier le format de la date
        try:
            first_date_parsed = datetime.strptime(first_date, "%Y-%m-%d")
            dates.append(first_date_parsed)
        except ValueError:
            invalid_entries.append({"Date": first_date, "Reason": "Invalid date format"})

        cash_flows.append(-initial_value)
        table.append({
            "Date": first_date,
            "Type d'Activité (activity_type)": dataset[0]["Type d'Activité (activity_type)"],
            "Sens Flux de Tréso": dataset[0]["Sens Flux de Tréso"],
            "Flux de trésorerie (net_amount)": -initial_value,
            "Valeur totale portefeuille (liquidités + titres détenus)": current_equity
        })

        # Traiter les autres lignes
        for item in dataset[1:]:
            date = item.get("Date")
            try:
                date_parsed = datetime.strptime(date, "%Y-%m-%d")
                dates.append(date_parsed)
            except ValueError:
                invalid_entries.append({"Date": date, "Reason": "Invalid date format"})
                continue

            net_amount = item.get("Flux de trésorerie (net_amount)", 0)
            if not isinstance(net_amount, (int, float)):
                invalid_entries.append({"Date": date, "Reason": "Invalid net_amount"})
                continue

            # Mettre à jour l'equity et ajouter aux flux
            current_equity += net_amount
            cash_flows.append(net_amount)

            # Ajouter au tableau pour le suivi
            table.append({
                "Date": date,
                "Type d'Activité (activity_type)": item.get("Type d'Activité (activity_type)"),
                "Sens Flux de Tréso": item.get("Sens Flux de Tréso"),
                "Flux de trésorerie (net_amount)": net_amount,
                "Valeur totale portefeuille (liquidités + titres détenus)": current_equity
            })

        # Ligne finale : Déterminer la dernière valeur et sa date
        last_valid_entry = None  # Initialiser une variable pour le dernier flux valide

        # Rechercher le dernier flux de trésorerie valide (net_amount)
        for item in reversed(dataset):  # Parcourir le dataset à l'envers
            net_amount = item.get("Flux de trésorerie (net_amount)", 0)
            if net_amount != 0:  # Vérifier si le flux est non nul
                last_valid_entry = item
                break

        if not last_valid_entry:  # Gérer le cas où aucun flux valide n'est trouvé
            return jsonify({
                "error": "No valid cash flow found to determine final portfolio value."
            }), 400

        # Récupérer la date et la valeur finale à partir du dernier flux valide
        final_date = last_valid_entry.get("Date")
        final_equity = last_valid_entry.get("Valeur totale portefeuille (liquidités + titres détenus)", 0)

        # Si la dernière valeur du portefeuille est absente, utiliser la dernière valeur mise à jour
        if not final_equity:
            final_equity = current_equity

        try:
            final_date_parsed = datetime.strptime(final_date, "%Y-%m-%d")
            dates.append(final_date_parsed)  # Ajouter la date finale
        except ValueError:
            invalid_entries.append({"Date": final_date, "Reason": "Invalid date format"})

        cash_flows.append(final_equity)  # Ajouter la valeur finale comme flux positif

        # Ajouter la ligne au tableau pour suivi
        table.append({
            "Date": final_date,
            "Type d'Activité (activity_type)": "Valeur finale (equity en date du dernier événement de trésorerie)",
            "Sens Flux de Tréso": "N/A",
            "Flux de trésorerie (net_amount)": final_equity,
            "Valeur totale portefeuille (liquidités + titres détenus)": final_equity
        })

        # Vérification finale : correspondance entre flux et dates
        if len(cash_flows) != len(dates):
            return jsonify({
                "error": "Mismatch between the number of cash flows and dates.",
                "cash_flows": cash_flows,
                "dates": [d.strftime("%Y-%m-%d") for d in dates],
                "invalid_entries": invalid_entries
            }), 400

        # Calcul du XIRR
        mwr_annualized = pyxirr.xirr(dates, cash_flows)  # Résultat brut
        mwr_percentage = mwr_annualized * 100

        # Réponse finale
        response = {
            "table": table,
            "MWR_annualized_percentage": round(mwr_percentage, 2),
            "MWR_annualized_raw": mwr_annualized,
            "cash_flows_used": cash_flows,
            "dates_used": [d.strftime("%Y-%m-%d") for d in dates],
            "invalid_entries": invalid_entries  # Liste des erreurs détectées
        }
        return jsonify(response), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True)
