from flask import Flask, request, jsonify
from datetime import datetime
import pyxirr

app = Flask(__name__)

# Route d'accueil (GET)
@app.route("/", methods=["GET"])
def home():
    return "Bienvenue sur l'API MWR Calculator. Utilisez /api/calculate pour soumettre des données.", 200

# Route principale pour le calcul du MWR
@app.route('/api/calculate', methods=['POST'])
def calculate_mwr():
    data = request.get_json()

    # Vérification des données d'entrée
    if not data or "dataset" not in data:
        return jsonify({"error": "Invalid input. Please provide a valid dataset."}), 400

    dataset = data["dataset"]

    # Initialisation des variables
    table = []
    cash_flows = []
    dates = []

    try:
        # Extraire la valeur initiale
        initial_value = dataset[0].get("User base_value_1D", 0)
        if not initial_value:
            return jsonify({"error": "Initial value 'User base_value_1D' is missing."}), 400

        # Ajouter la première ligne (valeur initiale)
        current_equity = initial_value
        cash_flows.append(-initial_value)  # Flux initial en négatif pour XIRR
        dates.append(dataset[0]["Date"])
        
        table.append({
            "Date": dataset[0]["Date"],
            "Type d'Activité (activity_type)": dataset[0]["Type d'Activité (activity_type)"],
            "Sens Flux de Tréso": dataset[0]["Sens Flux de Tréso"],
            "Flux de trésorerie (net_amount)": -initial_value,
            "Valeur totale portefeuille (liquidités + titres détenus)": current_equity
        })

        # Traiter les autres lignes du dataset
        for item in dataset[1:]:
            date = item.get("Date")
            activity_type = item.get("Type d'Activité (activity_type)")
            cash_flow_direction = item.get("Sens Flux de Tréso")
            net_amount = item.get("Flux de trésorerie (net_amount)", 0)

            # Calculer l'equity
            current_equity += net_amount
            cash_flows.append(net_amount)
            dates.append(date)

            # Ajouter chaque événement dans le tableau
            table.append({
                "Date": date,
                "Type d'Activité (activity_type)": activity_type,
                "Sens Flux de Tréso": cash_flow_direction,
                "Flux de trésorerie (net_amount)": net_amount,
                "Valeur totale portefeuille (liquidités + titres détenus)": current_equity
            })

        # Ligne finale : Valeur finale
        final_date = dates[-1]
        final_equity = current_equity
        table.append({
            "Date": final_date,
            "Type d'Activité (activity_type)": "Valeur finale (equity en date du dernier events de tréso)",
            "Sens Flux de Tréso": "N/A",
            "Flux de trésorerie (net_amount)": final_equity,
            "Valeur totale portefeuille (liquidités + titres détenus)": final_equity
        })

        # Calcul de XIRR
        mwr_annualized = pyxirr.xirr(dates, cash_flows)  # Résultat brut (décimal)
        mwr_percentage = mwr_annualized * 100  # Résultat en pourcentage

        # Réponse finale avec table et résultats MWR
        response = {
            "table": table,
            "MWR_annualized_percentage": round(mwr_percentage, 2),
            "MWR_annualized_raw": mwr_annualized  # Décimal brut
        }
        return jsonify(response), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True)
