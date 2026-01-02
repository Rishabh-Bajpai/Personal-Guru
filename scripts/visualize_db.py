import sys
import os

# Add the project root to the python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from app.core.models import Topic, StudyStep, Quiz, Flashcard
from sqlalchemy.orm import class_mapper

def generate_mermaid_er():
    app = create_app()
    with app.app_context():
        print("erDiagram")
        
        models = [Topic, StudyStep, Quiz, Flashcard]
        
        # Track processed relationships to avoid duplicates if needed, 
        # but Mermaid handles multiple lines fine usually.
        
        for model in models:
            mapper = class_mapper(model)
            table_name = model.__tablename__
            
            # Print Attributes
            print(f'    {table_name} {{')
            for column in mapper.columns:
                col_type = str(column.type).replace(" ", "_") # Clean spaces
                print(f'        {col_type} {column.name}')
            print('    }')
            
            # Print Relationships
            # simplified: only print for relationships explicitly defined on this model, 
            # effectively handling the One-to-Many usually defined on the One side.
            for prop in mapper.relationships:
                target_model = prop.mapper.class_
                target_table = target_model.__tablename__
                
                # Determine cardinality
                direction = prop.direction.name
                
                if direction == 'ONETOMANY':
                    print(f'    {table_name} ||--o{{ {target_table} : "{prop.key}"')
                elif direction == 'MANYTOONE':
                    print(f'    {table_name} }}o--|| {target_table} : "{prop.key}"')
                elif direction == 'MANYTOMANY':
                    print(f'    {table_name} }}o--o{{ {target_table} : "{prop.key}"')

if __name__ == '__main__':
    generate_mermaid_er()
