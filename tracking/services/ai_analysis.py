import polars as pl
from sklearn.linear_model import LinearRegression
from tracking.models import MeasurementSession, WeightMeasurement, PhysicalActivityLog, FoodLog
from django.utils import timezone

def generate_insights(user):
    """
    Recopila todos los datos históricos del usuario, los cruza por fecha y 
    utiliza Machine Learning (Regresión Lineal Simple y Correlaciones)
    para generar insights de salud.
    """
    # 1. Obtener datos crudos
    activities = PhysicalActivityLog.objects.filter(user=user).values('date', 'duration_minutes')
    
    foods_qs = FoodLog.objects.filter(user=user).prefetch_related('items__food', 'items__recipe__ingredients__food')
    foods_data = []
    for f in foods_qs:
        foods_data.append({
            'date': f.date,
            'eaten_out': f.eaten_out,
            'total_calories': f.get_total_calories()
        })
        
    weights = WeightMeasurement.objects.filter(user=user).values('date', 'weight')
    sessions = MeasurementSession.objects.filter(user=user).values('date', 'avg_systolic')

    # Si no hay suficientes datos básicos, salir.
    if not (activities.exists() or foods_data or weights.exists() or sessions.exists()):
        return {"insights": [], "scatter_data": [], "trendline_data": []}

    # 2. Convertir a Polars y agrupar por día (pueden haber varias mediciones/actividades al día)
    df_act = pl.DataFrame(list(activities))
    if df_act.height > 0:
        df_act = df_act.group_by('date').agg(pl.col('duration_minutes').sum().alias('sport_duration'))
    else:
        df_act = pl.DataFrame({"date": [], "sport_duration": []}, schema={"date": pl.Date, "sport_duration": pl.Int64})

    if foods_data:
        df_food = pl.DataFrame(foods_data)
        # Convert eaten_out to integer sum
        df_food = df_food.with_columns(pl.col("eaten_out").cast(pl.Int64))
        df_food = df_food.group_by('date').agg([
            pl.col('eaten_out').sum().alias('eat_out_count'),
            pl.col('total_calories').sum().alias('daily_calories')
        ])
    else:
        df_food = pl.DataFrame({"date": [], "eat_out_count": [], "daily_calories": []}, schema={"date": pl.Date, "eat_out_count": pl.Int64, "daily_calories": pl.Float64})

    df_weight = pl.DataFrame(list(weights))
    if df_weight.height > 0:
        df_weight = df_weight.with_columns(pl.col('weight').cast(pl.Float64))
        # Si hay varias mediciones de peso al día, tomar la última o media
        df_weight = df_weight.group_by('date').agg(pl.col('weight').mean().alias('weight'))
    else:
        df_weight = pl.DataFrame({"date": [], "weight": []}, schema={"date": pl.Date, "weight": pl.Float64})
        
    df_session = pl.DataFrame(list(sessions))
    if df_session.height > 0:
        df_session = df_session.filter(pl.col('avg_systolic').is_not_null())
        df_session = df_session.group_by('date').agg(pl.col('avg_systolic').mean().alias('avg_sys'))
    else:
        df_session = pl.DataFrame({"date": [], "avg_sys": []}, schema={"date": pl.Date, "avg_sys": pl.Float64})

    # 3. Unir todo (Full Outer Join para tener una línea de tiempo continua)
    dates_frames = [df for df in [df_act, df_food, df_weight, df_session] if df.height > 0]
    if not dates_frames:
        return {"insights": [], "scatter_data": []}
    
    # Obtener todas las fechas posibles
    all_dates = pl.DataFrame()
    for df in dates_frames:
        all_dates = pl.concat([all_dates, df.select('date')])
    all_dates = all_dates.unique().sort('date')
    
    # Join con las fechas
    df_master = all_dates
    for df in dates_frames:
        df_master = df_master.join(df, on='date', how='left')

    # Rellenar nulos con 0 para deporte y comidas (si no se registró, asumimos 0)
    if 'sport_duration' in df_master.columns:
        df_master = df_master.with_columns(pl.col('sport_duration').fill_null(0))
    else:
        df_master = df_master.with_columns(pl.lit(0).alias('sport_duration'))
        
    if 'eat_out_count' in df_master.columns:
        df_master = df_master.with_columns(pl.col('eat_out_count').fill_null(0))
    else:
        df_master = df_master.with_columns(pl.lit(0).alias('eat_out_count'))

    if 'daily_calories' in df_master.columns:
        df_master = df_master.with_columns(pl.col('daily_calories').fill_null(0.0))
    else:
        df_master = df_master.with_columns(pl.lit(0.0).alias('daily_calories'))

    # Para peso y tensión, hacemos forward fill (el peso de hace 2 días sirve hoy si no te has pesado)
    if 'weight' in df_master.columns:
        df_master = df_master.with_columns(pl.col('weight').forward_fill())
    else:
        df_master = df_master.with_columns(pl.lit(None).cast(pl.Float64).alias('weight'))
        
    if 'avg_sys' in df_master.columns:
        df_master = df_master.with_columns(pl.col('avg_sys').forward_fill())
    else:
        df_master = df_master.with_columns(pl.lit(None).cast(pl.Float64).alias('avg_sys'))

    # Nos aseguramos del forward fill
    df_master = df_master.sort('date')
    
    # Preparamos las variables "diferencia con el día anterior" o "al día siguiente"
    # Vamos a crear 'weight_next_day', para ver qué pasa con el peso al día siguiente
    df_master = df_master.with_columns([
        pl.col('weight').shift(-1).alias('weight_next_day'),
        pl.col('avg_sys').shift(-1).alias('sys_next_day'),
    ])
    df_master = df_master.with_columns([
        (pl.col('weight_next_day') - pl.col('weight')).alias('weight_diff_next'),
        (pl.col('sys_next_day') - pl.col('avg_sys')).alias('sys_diff_next'),
    ])

    insights = []

    # 4. Machine Learning: Regresión Lineal para Peso
    # ¿Afectan los minutos de deporte y calorias a la variación de peso del día siguiente?
    df_ml_weight = df_master.drop_nulls(subset=['sport_duration', 'daily_calories', 'weight_diff_next'])
    
    if df_ml_weight.height >= 10:  # Necesitamos un mínimo de datos para que sea estadístico
        X = df_ml_weight.select(['sport_duration', 'daily_calories']).to_numpy()
        y = df_ml_weight.select('weight_diff_next').to_numpy().ravel()
        
        reg_weight = LinearRegression()
        reg_weight.fit(X, y)
        coef_sport = reg_weight.coef_[0]
        coef_calories = reg_weight.coef_[1]

        # Insight Deporte -> Peso
        if coef_sport < -0.001:  # Al menos -1g por minuto
            gramos_por_30_min = abs(coef_sport * 30 * 1000)
            insights.append({
                "type": "success",
                "icon": "bi-lightning-charge",
                "title": "Impacto del Ejercicio",
                "text": f"Nuestra IA calcula que por cada 30 minutos de deporte diario, tu peso disminuye en media {gramos_por_30_min:.0f}g al día siguiente."
            })
            
        # Insight Comida -> Peso
        # Si calorías tiene impacto positivo, lo mostramos (coef > 0 que significa subir peso por kcal)
        if coef_calories > 0.0001: # Sube al menos 0.1g por cada 1 kcal -> 100g por 1000kcal
            insights.append({
                "type": "warning",
                "icon": "bi-exclamation-triangle",
                "title": "Impacto Calórico Neto",
                "text": f"Tu metabolismo indica que por cada 1,000 kcal aumentas aproximadamente {coef_calories * 1000 * 1000:.0f}g al día siguiente."
            })
            
    # 5. Machine Learning: Regresión Lineal para Tensión Sistólica
    df_ml_sys = df_master.drop_nulls(subset=['sport_duration', 'eat_out_count', 'sys_diff_next'])
    if df_ml_sys.height >= 10:
        X = df_ml_sys.select(['sport_duration', 'eat_out_count']).to_numpy()
        y = df_ml_sys.select('sys_diff_next').to_numpy().ravel()
        
        reg_sys = LinearRegression()
        reg_sys.fit(X, y)
        sys_food_coef = reg_sys.coef_[1]

        if sys_food_coef > 1.0: # Cada comida fuera sube 1mmHg o más
            insights.append({
                "type": "danger",
                "icon": "bi-heart-pulse",
                "title": "Alerta de Sodio / Comidas Fuera",
                "text": f"Comer fuera de casa está aumentando tu presión sistólica media en +{sys_food_coef:.1f} mmHg. ¡Vigila el exceso de sal en restaurantes!"
            })

    # 6. Preparar datos para el gráfico de dispersión (Deporte vs Peso Actual)
    scatter_data = []
    df_scatter = df_master.filter((pl.col('sport_duration') > 0) & (pl.col('weight').is_not_null()))
    
    for row in df_scatter.iter_rows(named=True):
        scatter_data.append({
            "x": row['sport_duration'],
            "y": row['weight']
        })

    # Calcular la línea de tendencia (Regresión Lineal simple del Scatter)
    trendline_data = []
    if df_scatter.height >= 2:
        try:
            X_sc = df_scatter.select('sport_duration').to_numpy()
            y_sc = df_scatter.select('weight').to_numpy().ravel()
            reg_sc = LinearRegression().fit(X_sc, y_sc)
            
            x_min = float(X_sc.min())
            x_max = float(X_sc.max())
            y_min = float(reg_sc.predict([[x_min]])[0])
            y_max = float(reg_sc.predict([[x_max]])[0])
            
            trendline_data = [{"x": x_min, "y": y_min}, {"x": x_max, "y": y_max}]
        except Exception:
            pass

    # Si la lista está vacía, metemos un insight genérico motivador
    if not insights:
         insights.append({
                "type": "info",
                "icon": "bi-info-circle",
                "title": "Insuficientes datos predictivos",
                "text": "Sigue registrando tu peso, comidas y deporte todos los días. Próximamente la IA tendrá datos suficientes para darte conclusiones personalizadas."
            })

    return {
        "insights": insights,
        "scatter_data": scatter_data,
        "trendline_data": trendline_data
    }
